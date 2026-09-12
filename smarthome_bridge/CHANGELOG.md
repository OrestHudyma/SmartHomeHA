# Changelog

## 0.1.2

- Check USB controller health every 10 minutes; retain 5-second reconnect retries.
- Repeat known Grow light ON/OFF states using the shared device refresh interval.
- Preserve unknown-state and connection-loss safeguards during lamp refresh.

## 0.1.1

- Use English device names, entity names, configuration labels and documentation.
- Preserve MQTT unique IDs and topics when updating display names.

## 0.1.0

- Home Assistant app for aarch64 and amd64 with MQTT Discovery.
- Configurable lamps, boiler interlock, fast commands and global day/night buttons.
- Selected serial port, bounded command queue and USB/MQTT recovery.
- Preserve upstream periphery.py and nmea.py; replace Telegram runtime.
- First experimental release; hardware acceptance must precede unattended use.
