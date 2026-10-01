# SmartHome Bridge

## Installation

Requires Home Assistant OS (64-bit), a USB/433 MHz controller and an MQTT 5 broker,
such as the official Mosquitto app. Configure the MQTT integration in HA.
Add `https://github.com/OrestHudyma/SmartHomeHA` to the app repositories and install
SmartHome Bridge. The initial build on a Raspberry Pi can take several minutes.

Select the controller port in Configuration, preferably `/dev/serial/by-id/...`.
Supervisor provides serial-device access, but the app opens only the selected port.
It does not scan unrelated Zigbee/Z-Wave adapters. A missing or busy controller is
reported as unavailable; reconnection is attempted every 5 seconds. An established
connection is checked every 600 seconds (10 minutes).

Save the configuration, start the app and inspect its logs. Entities appear in the
MQTT integration after connection. Enable Start on boot and, if desired, the
Supervisor watchdog after completing the acceptance checks.

## YAML configuration

Edit YAML in the app's Configuration tab. Supervisor passes it to the application
as `/data/options.json`; this is not Home Assistant's `configuration.yaml`.

```yaml
serial_port: /dev/serial/by-id/usb-YOUR_CONTROLLER
bridge_id: smarthome
devices:
  - type: boiler
    id: "1"
    name: Boiler
  - type: fito_lamp
    id: "1"
    name: Grow light - Kitchen
  - type: fito_lamp
    id: "2"
    name: Grow light - Balcony
  - type: global
    id: "1"
    name: Global controls
mqtt_host: ""
mqtt_port: 1883
mqtt_username: ""
mqtt_password: ""
mqtt_tls: false
discovery_prefix: homeassistant
ha_status_topic: homeassistant/status
refresh_seconds: 3600
log_level: INFO
```

An empty `mqtt_host` uses Supervisor MQTT service credentials (official Mosquitto).
For another broker, specify its host, port and credentials. `mqtt_tls: true` enables
TLS with certificate verification using the container's system CAs. Client
certificates and private CAs are not configurable in this version.
The MQTT account needs permission to publish Discovery and state messages and to
subscribe to bridge commands and `ha_status_topic`. If a subscription is denied,
fix permissions and restart the app. Restart the app to fetch new credentials if
Supervisor changes its MQTT password.

`bridge_id` must be unique on the broker. Avoid changing it or existing device IDs:
they determine entity identity and persisted interlocks. Changing `name` updates
display names without creating new entities. Home Assistant keeps existing
`entity_id` values, including IDs generated from names used by previous versions.
The grow light ID is sent as a string and must exactly match its firmware.
Format validation cannot establish that a physical device exists.

To add another grow light, add a device entry, save and restart the app. A second
boiler is not supported because the current boiler protocol has no address.
Only one `global` group is allowed. Removed entries have their Discovery
configurations cleared on the next app start.

## State and command behavior

Power represents the **last successfully transmitted command**, not measured
physical state. Entity attributes include `physical_state_confirmed: false`.
Power is unknown after startup, USB recovery or MQTT reconnection. An initial
`power=True` in an upstream hardware class does not cause a power-on command.
The user or an HA automation must issue a new command. Global DAY/NIGHT make lamp
states unknown; global ALARM makes all device power states unknown and suspends
their periodic power refresh. Enabled interlocks are unchanged. Global Alarm is
an event, never a periodically refreshed mode. Receivers must implement
`$SHGLB,ALARM,*01` followed by LF; no device ID is sent. Old addressed Alarm
buttons are removed on discovery synchronization; migrate their automations to
Global controls Alarm. There is no individual acknowledgement. Firmware schedules
can change physical state independently of the last transmitted command.

The boiler's **Enabled** interlock is saved in `/data/state.json`. Disabling it
persists the restriction before sending OFF. Failed OFF transmission does not
release the interlock, but it also does not prove the device physically switched
off. Repeat OFF after connectivity returns (the automation example does this).
Enabling the interlock alone sends no ON command. A corrupt state file prevents
startup; restore a backup to preserve the restriction. This is a software interlock,
not a substitute for thermal protection or a physical switch. It does not change
the boiler firmware's autonomous behavior.

Commands execute sequentially, with a queue limit of 32 and a lifetime of 10 seconds.
Retained commands are rejected, including live retained deliveries. The MQTT session
does not queue commands while disconnected. MQTT QoS 1 can duplicate delivery;
commands specify ON/OFF rather than TOGGLE. Repeated commands may reset firmware timers.

On a serial error the connection closes, power states become unknown, control
becomes unavailable and queued commands are invalidated. An in-progress serial
transmission is not interrupted halfway by MQTT loss; remaining stale commands are
not executed. A clean shutdown publishes `offline`. An unclean disconnect relies on
the broker's Last Will after connection-loss or keepalive detection.

## Schedule

The app has no calendar schedule. Paste
[`examples/boiler_schedule.yaml`](../examples/boiler_schedule.yaml) into the YAML
editor for one HA automation. Replace its three entity IDs with the actual IDs in
your HA instance. Time is interpreted in Home Assistant's configured timezone:
05:00-22:00 means ON when enabled; all other times mean OFF.

The automation also reconciles state after HA startup, restored availability and
interlock changes. Consequently, enabling the boiler during daytime can turn it
on through this automation. A manual command lasts until the next schedule trigger.

`refresh_seconds` repeats known Boiler and Grow light states (default: 3600 seconds;
range: 60-3600). Each configured lamp receives its own addressed ON/OFF command.
After Fast on/off, repeats use ordinary ON/OFF, matching the original server's
`FitoLamp.refresh()` behavior; they do not replay fast commands or global broadcasts.
Repeated commands can renew firmware override timers; they are not physical-state
acknowledgments. Unknown states, including lamp states invalidated by global
day/night commands, are not repeated. Repeats stop when USB is unavailable,
MQTT disconnects or HA reports `offline`; state must be reconciled after recovery.
Detection of an HA crash depends on its MQTT Last Will. Without Birth/Will messages,
the app cannot detect HA loss while the broker remains available. Keep the default
Birth/Will messages on `homeassistant/status`. Physical behavior when no commands
arrive is determined by each device's firmware.

## Updates, backups and rollback

Back up the app before updating through Home Assistant. Supervisor builds the
container for the selected version. HA can enable automatic updates, but manually
verify control after updating this experimental version. App backups include
options and `/data/state.json`. To roll back, restore the previous app backup
together with its data.

## Acceptance checks

1. Verify the selected USB port and stop any competing process that owns it.
2. Start the app: expect USB available, unknown power and no ON commands.
3. At an agreed time, test boiler and lamp OFF/ON commands and fast buttons.
4. Disable the boiler, restart the app and confirm that ON remains blocked.
5. Restart HA/MQTT and reconnect USB: no duplicate entities or stale commands.
6. Add the automation and verify timezone and restart recovery.
7. Complete these checks before leaving the system unattended.
