import json
import logging
import paho.mqtt.client as mqtt
from paho.mqtt.subscribeoptions import SubscribeOptions

LOG = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self, settings, credentials):
        self.settings, self.credentials = settings, credentials
        self.controller = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"smarthome_{settings.bridge_id}", protocol=mqtt.MQTTv5)
        host, port, username, password = credentials
        if username:
            self.client.username_pw_set(username, password)
        if settings.mqtt_tls:
            self.client.tls_set()  # Certificate verification remains enabled.
        self.client.will_set(f"{settings.prefix}/availability", "offline", qos=1, retain=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.max_queued_messages_set(256)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_connect_fail = lambda client, userdata: LOG.warning("MQTT connection failed; retrying")
        self.subscribed = False
        self.client.on_subscribe = self._on_subscribe

    def start(self, controller):
        self.controller = controller
        self.client.connect_async(self.credentials[0], self.credentials[1], keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            LOG.error("MQTT connection refused")
            return
        self.subscribed = False
        client.publish(f"{self.settings.prefix}/availability", "offline", qos=1, retain=True)
        # MQTT5 keeps the retain flag on live messages too, so retained ON is always rejected.
        client.subscribe([(f"{self.settings.prefix}/+/+/set", SubscribeOptions(qos=1, retainAsPublished=True)),
                          (self.settings.ha_status_topic, SubscribeOptions(qos=1))])

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            LOG.error("MQTT subscription denied; check broker permissions")
            client.disconnect()
            return
        self.subscribed = True
        self.controller.network_changed(True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.subscribed = False
        self.controller.network_changed(False)

    def _on_message(self, client, userdata, message):
        if message.topic == self.settings.ha_status_topic:
            if message.payload in (b"online", b"offline"):
                self.controller.home_assistant_status(message.payload == b"online")
            return
        prefix = self.settings.prefix + "/"
        if not message.topic.startswith(prefix) or len(message.payload) > 32:
            return
        parts = message.topic[len(prefix):].split("/")
        if len(parts) != 3 or parts[2] != "set":
            return
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            return
        if not self.controller.submit(parts[0], parts[1], payload, message.retain):
            LOG.warning("Rejected command: invalid, retained, busy or controller unavailable")

    def publish(self, topic, payload, retain=True):
        if not self.client.is_connected():
            return False  # State will be freshly published after reconnection.
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)
        info = self.client.publish(topic, payload, qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            LOG.warning("MQTT publication failed; scheduling a fresh snapshot")
            if self.controller:
                self.controller.resync.set()
            return False
        return True

    def close(self):
        if self.client.is_connected():
            info = self.client.publish(f"{self.settings.prefix}/availability", "offline", qos=1, retain=True)
            try:
                info.wait_for_publish(timeout=3)
            except (RuntimeError, ValueError):
                LOG.warning("Could not confirm offline publication")
        self.client.disconnect()
        self.client.loop_stop()
