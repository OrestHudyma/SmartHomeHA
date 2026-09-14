"""One hardware owner. MQTT callbacks only enqueue bounded, short-lived commands."""
from dataclasses import dataclass
import logging
from queue import Empty, Full, Queue
import threading
import time

from devices.registry import REGISTRY
from discovery import discovery_messages
from hardware_adapter import HardwareAdapter

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Command:
    key: str
    action: str
    payload: str
    generation: int
    expires: float


class Controller:
    HEALTH_CHECK_SECONDS = 600

    def __init__(self, settings, store, publish, hardware_factory=HardwareAdapter, clock=time.monotonic):
        self.settings, self.store, self.publish = settings, store, publish
        self.hardware_factory, self.clock = hardware_factory, clock
        self.hardware = None
        self.adapters = {c.key: REGISTRY[c.type](c, None) for c in settings.devices}
        self.states = {c.key: {"power": None, "enabled": store.enabled(c.key), "result": "unknown"}
                       for c in settings.devices}
        self.commands = Queue(maxsize=32)
        self.lock = threading.Lock()
        self.connected = False
        self.ha_online = True
        self.ready = False
        self.generation = 0
        self.seen_generation = -1
        self.resync = threading.Event()
        self.next_connect = self.next_health = 0
        self.next_refresh = self.clock() + settings.refresh_seconds

    def network_changed(self, connected):
        with self.lock:
            self.connected, self.ready = connected, False
            self.generation += 1
        self.resync.set()

    def submit(self, key, action, payload, retained=False):
        adapter = self.adapters.get(key)
        if retained or adapter is None or payload not in adapter.actions.get(action, ()):
            return False
        with self.lock:
            if not self.connected or not self.ready:
                return False
            command = Command(key, action, payload, self.generation, self.clock() + 10)
            try:
                self.commands.put_nowait(command)
            except Full:
                return False
        return True

    def home_assistant_status(self, online):
        with self.lock:
            self.ha_online = online
            if not online:
                self.ready = False
                self.generation += 1
        self.resync.set()

    def _emit(self, suffix, payload):
        self.publish(f"{self.settings.prefix}/{suffix}", payload, True)

    def publish_states(self):
        for key, state in self.states.items():
            adapter = self.adapters[key]
            if adapter.power_domain:
                self._emit(f"{key}/power/state", state["power"] or "None")
                self._emit(f"{key}/attributes", {"state_source": "last_successful_transmission",
                                                "physical_state_confirmed": False})
            if adapter.config.type == "boiler":
                self._emit(f"{key}/enabled/state", "ON" if state["enabled"] else "OFF")
            self._emit(f"{key}/result", state["result"])

    def _unknown_power(self):
        for key, adapter in self.adapters.items():
            self.states[key]["power"] = None
            if adapter.power_domain:
                adapter.device.power = False

    def _drop_hardware(self):
        with self.lock:
            self.ready = False
            self.generation += 1
        if self.hardware is not None:
            try:
                self.hardware.close()
            except OSError:
                LOG.warning("Error closing serial port")
        self.hardware = None
        self._unknown_power()
        self.next_connect = self.clock() + 5
        self._emit("hardware", "offline")
        self.publish_states()

    def _connect_hardware(self):
        if self.hardware is not None or self.clock() < self.next_connect:
            return
        try:
            self.hardware = self.hardware_factory(self.settings.serial_port)
            for key, adapter in self.adapters.items():
                adapter.device.interface = self.hardware
                if adapter.config.type == "boiler":
                    adapter.device.enabled = self.states[key]["enabled"]
            self.next_health = self.clock() + self.HEALTH_CHECK_SECONDS
            self.resync.set()
        except (OSError, ValueError, ConnectionError):
            LOG.warning("USB controller unavailable; retrying in 5 seconds")
            self._drop_hardware()

    def _sync(self):
        messages = discovery_messages(self.settings)
        published = True
        # Only delete discovery configs which this instance previously published.
        for topic in set(self.store.data["discovery_topics"]) - set(messages):
            published = self.publish(topic, "", True) and published
        for topic, payload in messages.items():
            published = self.publish(topic, payload, True) and published
        if not published:
            self.resync.set()  # Keep ownership so failed removals can be retried.
        elif sorted(messages) != self.store.data["discovery_topics"]:
            self.store.set_discovery_topics(messages)
        self.publish_states()
        self._emit("hardware", "online" if self.hardware is not None else "offline")
        self._emit("availability", "online")
        with self.lock:
            self.ready = self.connected and self.ha_online and self.hardware is not None

    def tick(self):
        with self.lock:
            connected, generation = self.connected, self.generation
        if generation != self.seen_generation:
            self.seen_generation = generation
            self._unknown_power()
            self.next_refresh = self.clock() + self.settings.refresh_seconds
        if not connected:
            return  # No repeating ON commands while HA cannot reach the broker.
        self._connect_hardware()
        if self.resync.is_set():
            self.resync.clear()
            self._sync()
        if self.hardware is None:
            return
        # Process at most one command per tick, preserving fairness for health checks.
        try:
            command = self.commands.get_nowait()
        except Empty:
            command = None
        if command:
            with self.lock:
                valid = (self.connected and self.ready and command.generation == self.generation
                         and command.expires >= self.clock())
            if valid:
                self._execute(command)
        if self.hardware is not None and self.clock() >= self.next_health:
            try:
                if not self.hardware.test():
                    raise ConnectionError("Controller health check failed")
                self.next_health = self.clock() + self.HEALTH_CHECK_SECONDS
            except (OSError, ValueError, ConnectionError):
                self._drop_hardware()
        if self.hardware is not None and self.clock() >= self.next_refresh:
            self.next_refresh = self.clock() + self.settings.refresh_seconds
            for key, adapter in self.adapters.items():
                with self.lock:
                    online, generation = self.connected and self.ready and self.ha_online, self.generation
                power = self.states[key]["power"]
                if online and adapter.config.type in ("boiler", "fito_lamp") and power is not None:
                    self._execute(Command(key, "power", power, generation, self.clock() + 10))

    def _execute(self, command):
        adapter, state = self.adapters[command.key], self.states[command.key]
        action, payload = command.action, command.payload
        if action == "enabled":
            enabled = payload == "ON"
            # Commit the interlock before acknowledging it or sending hardware commands.
            if not enabled:
                state["enabled"] = adapter.device.enabled = False
                state["power"] = None
            try:
                self.store.set_enabled(command.key, enabled)
            except OSError:
                if not enabled:
                    # A failed save must not prevent attempting the requested power-off.
                    try:
                        adapter.device.power_off()
                    finally:
                        raise
                raise
            state["enabled"] = adapter.device.enabled = enabled
            if enabled:
                state["result"] = "enabled; no power command sent"
                self.publish_states()
                return
            action, payload = "power", "OFF"
        if action == "power" and payload == "ON" and not state["enabled"]:
            state["result"] = "rejected: boiler disabled"
            self.publish_states()
            return
        try:
            response = adapter.execute(action, payload)
            if response != "ok":
                state["result"] = "transmission failed"
                self._drop_hardware()  # Do not match a late ACK to the next command.
                return
        except (OSError, ValueError, ConnectionError):
            state["result"] = "transmission failed"
            self._drop_hardware()
            return
        with self.lock:
            still_current = self.connected and command.generation == self.generation
        if not still_current:
            self._unknown_power()
            return
        state["result"] = "ok"
        if action == "power":
            state["power"] = payload
        elif action in ("fast_on", "fast_off"):
            state["power"] = "ON" if action == "fast_on" else "OFF"
        elif action == "alarm":
            # A transient effect has no completion ACK. Do not refresh stale power.
            state["power"] = None
        elif adapter.config.type == "global":
            # Broadcasts can affect lamps; without feedback their individual states are unknown.
            for key, other in self.adapters.items():
                if other.config.type == "fito_lamp":
                    self.states[key]["power"] = None
        self.publish_states()

    def close(self):
        with self.lock:
            self.ready = False
        self._unknown_power()
        self.publish_states()
        self._emit("hardware", "offline")
        self._emit("availability", "offline")
        if self.hardware is not None:
            self.hardware.close()
            self.hardware = None
