# SmartHome Bridge

Control a SmartHome boiler and addressed grow lights through Home Assistant MQTT.
Configure the USB port and device list in this app's Configuration tab.

**Global controls** exposes an **Alarm** button. It broadcasts `SHGLB,ALARM`
without a device address, like DAY/NIGHT. Every receiver implementing that command
may react, including receivers not listed in the bridge configuration. Unsupported
receivers ignore it. This is not a safety alarm or a confirmed device status.
The controller ACK confirms transmission only.

All configured device power states become unknown after Alarm, suspending periodic
power refresh until a new power command is sent to each device. Boiler Enabled is
unchanged. Alarm is never periodically replayed. Explicit commands and HA
automations are not blocked by Alarm; avoid automatic unknown-state recovery that
would override an effect.

Upgrade receiver firmware to support global Alarm before using the new button.
The updated FitoLamp firmware retains its 20 fade-out/fade-in cycles, restores the
previous target brightness, and enables its three-hour manual override.
The old per-lamp Alarm button is removed from MQTT discovery on synchronization;
update dashboards and automations to the new Global controls Alarm entity.
The new command topic is `<prefix>/global_1/alarm/set` (payload `PRESS`), not a
per-lamp topic. No legacy addressed Alarm alias is exposed by the bridge.

The RF transport still sends its standard three copies; firmware does not provide
an effect-completion ACK or an exactly-once execution guarantee. Current firmware
blocks normal command processing during the effect, so do not rely on immediate
cancellation with OFF.

See [DOCS.md](DOCS.md) for setup, state semantics, interlock behavior and recovery.
