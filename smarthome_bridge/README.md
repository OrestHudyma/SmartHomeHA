# SmartHome Bridge

Control a SmartHome boiler and addressed grow lights through Home Assistant MQTT.
Configure the USB port and device list in this app's Configuration tab.

Grow lights expose an **Alarm** button, requiring firmware with `SHFTL,ALARM`
support. The current firmware runs 20 fade-out/fade-in cycles and targets full
brightness afterwards, with a three-hour manual override. This is not a safety
alarm or a confirmed device status. The controller ACK confirms transmission only.
Power becomes unknown after pressing Alarm, suspending periodic power refresh
until a new power command is sent. Alarm is never periodically replayed.
The RF transport still sends its standard three copies; firmware does not provide
an effect-completion ACK or an exactly-once execution guarantee. Current firmware
blocks normal command processing during the effect, so do not rely on immediate
cancellation with OFF.

See [DOCS.md](DOCS.md) for setup, state semantics, interlock behavior and recovery.
