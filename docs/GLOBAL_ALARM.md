# Global Alarm migration (2026-10-01)

Accepted protocol: `$SHGLB,ALARM,*01\n`, broadcast without a receiver ID.
Bridge 0.1.4 exposes Alarm under Global controls, not under individual lamps.
The pinned upstream periphery.py and nmea.py are unchanged.

Receivers independently decide how to react. This PR does not add an Alarm
reaction to the boiler firmware. The USB/433 interface already forwards SHGLB;
its code requires no protocol change.

All configured power states become unknown after successful transmission,
preventing stale periodic ON/OFF from interrupting any receiver's effect.
Enabled interlocks remain unchanged. Explicit commands and existing automations
can still supersede Alarm. Serial ACK does not prove radio reception/completion.

Deploy the companion FitoLamp global-Alarm firmware first, then upgrade Bridge.
Replace old per-lamp Alarm references in dashboards/automations with the new
Global controls Alarm entity. Owned old discovery entries are cleared using the
existing discovery-topic inventory. No legacy topic alias broadcasts unexpectedly.
Transport repeats and MQTT QoS 1 mean this is not exactly-once delivery.

Implementation is prepared in isolated worktrees to preserve the existing open
HW/ASUS PR and the user's dirty PSoC Designer project. No HA deployment, service
restart, merge or hardware flashing is performed by this change.

Verification: bridge unit tests and upstream-byte check pass locally. MQTT/PTY
integration requires the isolated CI broker/Linux environment. Firmware host
tests are in the companion FitoLamp repository; target build and physical tests
must be reported separately.
