import argparse
import logging
import os
import signal
import threading

from controller import Controller
from mqtt_bridge import MQTTBridge
from settings import Settings, mqtt_credentials
from state_store import StateStore

LOG = logging.getLogger(__name__)


def run(options="/data/options.json", state="/data/state.json", stop=None):
    settings = Settings.load(options)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = StateStore(state)
    if not settings.mqtt_host and not os.environ.get("SUPERVISOR_TOKEN"):
        raise ValueError("Configure mqtt_host when running outside Home Assistant Supervisor")
    stop = stop or threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            credentials = mqtt_credentials(settings, os.environ.get("SUPERVISOR_TOKEN"))
            break
        except (OSError, ValueError, KeyError):
            LOG.warning("MQTT service configuration unavailable; retrying in 10 seconds")
            stop.wait(10)
    if stop.is_set():
        return
    bridge = MQTTBridge(settings, credentials)
    controller = Controller(settings, store, bridge.publish)
    try:
        bridge.start(controller)
        LOG.info("SmartHome Bridge started; waiting for MQTT and USB")
        while not stop.is_set():
            controller.tick()
            stop.wait(0.05)
    finally:
        try:
            controller.close()
        finally:
            bridge.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", default="/data/options.json")
    parser.add_argument("--state", default="/data/state.json")
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()
    if args.check_config:
        Settings.load(args.options)
        print("Configuration valid")
    else:
        try:
            run(args.options, args.state)
        except ValueError as exc:
            LOG.error("Invalid configuration: %s", exc)
            raise SystemExit(1)
        except Exception as exc:
            # Keep secrets, URLs and arbitrary device responses out of logs.
            LOG.error("Bridge stopped: %s", type(exc).__name__)
            raise SystemExit(1)
