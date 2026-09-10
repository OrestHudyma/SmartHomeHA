# SmartHomeHA

Home Assistant app for the SmartHome USB/433 MHz controller, boiler and grow lights.
Targets Home Assistant OS on Raspberry Pi 4 (64-bit/aarch64) and amd64.

## Install

1. Install/configure the official Mosquitto broker app and the MQTT integration.
2. Add `https://github.com/OrestHudyma/SmartHomeHA` to your Home Assistant app repositories.
3. Install **SmartHome Bridge**, select the controller serial port in Configuration,
   check the device list, save and start the app.
4. Entities appear under the MQTT integration. Enable **Start on boot** if desired.

The app is built locally by Supervisor from a pinned Python image. No registry login
is required. Updating the app version through Home Assistant rebuilds the image;
there is no Git self-update or host Python discovery inside the container.

Read [configuration and operation](smarthome_bridge/DOCS.md), the
[boiler schedule example](examples/boiler_schedule.yaml) and the
[development guide](DEVELOPMENT.md).

## Scope and state semantics

- Boiler power and persistent software enable/disable interlock.
- Multiple addressed grow lights, normal power and fast on/off buttons.
- Global day/night buttons and USB connection diagnostics.
- MQTT Discovery, broker/USB reconnect, bounded commands and graceful shutdown.
- No Telegram code or dependencies in the current version.

Power entities represent the **last successfully transmitted command**, not measured
relay state. The serial `ok` response does not establish that a radio receiver acted
on the command. No temperature, power usage or physical connectivity is fabricated.

The original `periphery.py` and `nmea.py` are byte-identical to upstream commit
`da75b65a0b369643ea16cf762d19d835975c3e21`. Their SHA-256 hashes are recorded in
[upstream.json](upstream.json) and checked in CI. Git history is preserved.

Version 0.1.1 is experimental pending acceptance on the actual controller. Moving
the controller from the old server is required before production deployment; only
one process should own the USB port.
