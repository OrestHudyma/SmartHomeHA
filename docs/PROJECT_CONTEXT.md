# Project context

Prepared: **2026-09-21**, using the **2026-09-20** verification snapshot.
This file records architecture and access locations;
[DECISIONS.md](DECISIONS.md) records behavior, and [HANDOFF.md](HANDOFF.md) records
the current work. Do not use this as a substitute for checking live configuration.

Evidence labels used throughout these documents:

- **VERIFIED**: inspected source, Git state, test output or external status; the
  accompanying date/source defines what was actually checked.
- **AGREED**: accepted requirement; not necessarily implemented or deployed.
- **REPORTED / SCREENSHOT**: user report or visible UI; not a runtime test.
- **TO VERIFY**: historical detail or unresolved state needing fresh evidence.

## Repositories and components

**VERIFIED 2026-09-20**, local tree and Git remotes:

| Component | Location / responsibility |
| --- | --- |
| Active HA repository | `C:\Work\SmartHomeServer\SmartHomeHA`; [OrestHudyma/SmartHomeHA](https://github.com/OrestHudyma/SmartHomeHA) |
| Legacy standalone server | Parent checkout `C:\Work\SmartHomeServer`; [SmartHomeServer](https://github.com/OrestHudyma/SmartHomeServer), also the HA repo's `upstream` remote |
| Bridge | `smarthome_bridge/app/`: MQTT Discovery, device adapters, command queue, serial connection, persistent interlock |
| USB/433 firmware | `SmartHome_HW/HW_interface.cydsn/main.c`; workspace `SmartHome_HW/SmartHome_HW.cywrk`, PSoC Creator 4.4 |
| ASUS companion | `extras/asus-kiosk/`, `extras/asus-brightness/`; separate OS/HA installation, not part of the bridge image |
| Grow light firmware | Local file exists at `C:\Work\FitoLamp\FW\Slave\FitoLamp_slave_PSoC1\FitoLamp_slave\FitoLamp_slave\main.c`; separate [FitoLamp repository](https://github.com/OrestHudyma/FitoLamp) |
| Boiler firmware | Separate [Boiler repository](https://github.com/OrestHudyma/Boiler); current source/thresholds not inspected for this snapshot |

The bridge has no Telegram dependency or management layer. It is a Supervisor
source-built app, version **0.1.3**, marked **experimental**, supporting `aarch64`
and `amd64`. It uses pinned Python 3.13 in its container. The old standalone
launcher and host-Python discovery are not its update mechanism.
Sources: [README](../README.md), [config](../smarthome_bridge/config.yaml),
[development guide](../DEVELOPMENT.md).

## Deployment inventory

The following are **historical deployment records / user reports**, not a live
SSH check on 2026-09-20. Verify before use or change.

| System | Known location and role |
| --- | --- |
| Raspberry Pi 4 | Home Assistant OS; `192.168.0.127`, `homeassistant.local`; SSH app, previously `root` on port 22 |
| Home Assistant browser | `http://homeassistant.local/` or `http://192.168.0.127/` worked in the user's browser; do not assume an externally exposed port 8123 |
| HA apps | Mosquitto plus MQTT integration; SmartHome Bridge; SSH app. Last observed bridge slug `998a990c_smarthome_bridge`, version 0.1.3, autostart/watchdog enabled |
| ASUS Eee PC 901 | Lubuntu wall panel, `192.168.0.125`, user `orest`; Firefox dashboard `http://192.168.0.127/wall-panel/0` |
| USB/433 controller | Moved from the old Lubuntu server to the Pi, per user report; exact current serial path must be read from HA |
| Zigbee coordinator | User connected SONOFF **ZBDongle-P (CC2652P)**; installation/pairing status is not verified |

Last historical HA observation: OS 18.2, Core 2026.9.2, SSH app 10.4.0, Mosquitto
7.1.1. These are not required or guaranteed current versions.

SSH passwords were supplied in the conversation but are intentionally omitted.
Use an existing authorized credential source or request credentials securely if
unavailable. Never reconstruct secrets from example files or publish them in logs.

## Bridge behavior

**VERIFIED 2026-09-20**, [controller](../smarthome_bridge/app/controller.py),
[hardware adapter](../smarthome_bridge/app/hardware_adapter.py),
[device adapters](../smarthome_bridge/app/devices/),
[operation guide](../smarthome_bridge/DOCS.md):

- Device types: `boiler`, `fito_lamp`, `global`. Another lamp instance needs an
  addressed entry in app options; a new device type needs adapter/schema/tests.
- HA talks through MQTT to one serial owner, then through the USB/433 controller
  to radio receivers. A serial `ok` acknowledges transmission, not receiver action.
- Power represents the last successfully transmitted command, not measured relay
  state. No temperature or energy measurement is invented from this value.
- `Enabled` is the boiler's persistent software interlock. Disabling attempts OFF;
  enabling alone does not transmit ON. It is not a certified hardware safety layer.
- Grow light exposes `Power`, `Fast on`, `Fast off`, `Alarm`. Firmware determines
  the actual fade/effect behavior; the HA design uses normal Power for slow changes.
- The addressed `ALARM` extension is in a subclass, leaving upstream Python files
  unchanged. Alarm makes lamp power unknown and is not periodically replayed.
- Global DAY/NIGHT broadcasts can affect receivers implementing these commands;
  actual receiver support depends on firmware. Bridge invalidates all lamp power
  afterward rather than asserting a known physical state.
- Unknown power is not refreshed. MQTT/USB interruptions invalidate known power;
  a blanket automation on `unknown` could overwrite an Alarm or global mode.

| Timing / bound | Source value, not a live-options reading |
| --- | --- |
| USB controller health check | 600 seconds (10 minutes) |
| USB reconnect retry | 5 seconds |
| Known boiler/lamp power refresh | `refresh_seconds`, default 3600; allowed 60-3600 seconds |
| Pending command queue | 32 commands, 10-second expiry; rejects retained commands |

The 10-minute health probe and periodic RF power refresh are different operations.
Neither proves reception at a one-way device.

## Configuration and access locations

- App settings: HA **SmartHome Bridge -> Configuration**; inside the container
  `/data/options.json`. State/interlock: `/data/state.json`. Do not commit either.
- MQTT discovery uses `homeassistant` by default; with bridge ID `smarthome`, the
  command/state prefix is `smarthome/smarthome`. Check actual options before reuse.
- App update: refresh its repository in HA and update/rebuild the app. Updating
  bridge code does **not** deploy ASUS files or HA automation YAML.
- Shared Day/Night helpers/scripts: `/config/packages/day_night.yaml`.
- UI-editable automation entries: `/config/automations.yaml`, each with a unique
  `id`; preserve `automation: !include automations.yaml`. Local split-package
  migration files are included in this change set; see HANDOFF for publication status.
- ASUS service: `/opt/asus-brightness/brightness.py`,
  `/etc/systemd/system/asus-brightness.service`; private MQTT credentials at
  `/etc/asus-brightness/mqtt.json`, root-owned mode 600. Only the location belongs
  in these documents. [ASUS installation notes](../extras/README.md).

Safe diagnostic examples, **on the appropriate remote host**:

```sh
# HA SSH app: inspect, do not restart/update.
ha apps info 998a990c_smarthome_bridge
ha apps logs 998a990c_smarthome_bridge
# ASUS: inspect, do not publish commands or change brightness.
systemctl status asus-brightness
journalctl -u asus-brightness -n 30 --no-pager
```

Logs/configuration can contain sensitive data: inspect narrowly and redact output.

## Verification

From the **SmartHomeHA root**, using Python 3.10+ with
`requirements-dev.txt` already installed:

```sh
python scripts/check_upstream.py
python -m unittest discover -s smarthome_bridge -p test.py -v
python -m unittest discover -s extras/asus-brightness -p 'test_*.py' -v
python SmartHome_HW/test.py -v
```

Local verified executables: `.tools/release-venv/Scripts/python.exe` (Python 3.11)
and `C:\msys64\ucrt64\bin\gcc.exe`. These are machine-specific conveniences, not
repository dependencies. Set `CC` for the HW harness if GCC is not on PATH.

Bridge tests use mocks; integration tests need an isolated Mosquitto broker via
`MQTT_TEST_PORT` (CI uses 18884), and serial PTY testing needs Linux. Do not point
tests at the household broker. HW host tests compile real `main.c` with PSoC stubs;
Linux CI adds ASan/UBSan via `HW_TEST_SANITIZERS=1`. They do not flash hardware.

Container builds and target PSoC builds are separate checks. See
[DEVELOPMENT.md](../DEVELOPMENT.md) and [HW README](../SmartHome_HW/README.md).
Exact results for this snapshot are in [HANDOFF.md](HANDOFF.md).
