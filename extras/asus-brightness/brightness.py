#!/usr/bin/python3
"""Receive retained brightness commands for the ASUS wall display."""
import json
import logging
import signal
import threading
from pathlib import Path
import paho.mqtt.client as mqtt

BASE = 'wallpanel/asus/brightness'
BACKLIGHT = Path('/sys/class/backlight/intel_backlight')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def raw_brightness(payload, maximum):
    text = payload.decode('ascii')
    if not text.isdigit() or not 1 <= int(text) <= 100:
        raise ValueError('brightness must be an integer from 1 to 100')
    return max(1, int(maximum * int(text) / 100 + 0.5))


def main():
    config = json.loads(Path('/etc/asus-brightness/mqtt.json').read_text())
    stop = threading.Event()
    client = mqtt.Client(client_id='asus-wallpanel-brightness')
    client.username_pw_set(config['username'], config['password'])
    client.will_set(BASE + '/availability', 'offline', qos=1, retain=True)
    client.reconnect_delay_set(min_delay=2, max_delay=60)

    def connected(client, userdata, flags, rc):
        if rc != 0:
            logging.error('MQTT connection rejected: %s', rc)
            return
        client.subscribe(BASE + '/set', qos=1)
        client.publish(BASE + '/availability', 'online', qos=1, retain=True)
        logging.info('MQTT connected; subscribed for brightness commands')

    def message(client, userdata, msg):
        try:
            maximum = int((BACKLIGHT / 'max_brightness').read_text())
            value = raw_brightness(msg.payload, maximum)
            (BACKLIGHT / 'brightness').write_text(str(value))
            actual = int((BACKLIGHT / 'brightness').read_text())
            client.publish(BASE + '/state', json.dumps({
                'requested_percent': int(msg.payload), 'raw': actual,
                'maximum': maximum}), qos=1, retain=True)
            logging.info('Backlight applied: %s%% (%s/%s)', int(msg.payload), actual, maximum)
        except (ValueError, UnicodeError, OSError):
            logging.exception('Could not apply brightness command')

    client.on_connect = connected
    client.on_message = message
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    client.connect_async(config['host'], config['port'], keepalive=60)
    client.loop_start()
    stop.wait()
    client.publish(BASE + '/availability', 'offline', qos=1, retain=True).wait_for_publish()
    client.disconnect()
    client.loop_stop()


if __name__ == '__main__':
    main()
