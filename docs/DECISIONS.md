# Decisions and operating intent

Prepared: **2026-09-21**, using the **2026-09-20** snapshot and prior agreements.
Labels are defined in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).
Only the latest agreement is retained; older chat suggestions are not cumulative
requirements. Link implementation evidence and update the date when a decision changes.

## Architecture and source integrity

**AGREED; VERIFIED in local source:** maintain a separate Home Assistant app
repository derived from SmartHomeServer, with preserved Git history, MQTT
Discovery, no Telegram control, and optional companions outside the app container.

`smarthome_bridge/app/periphery.py` and `nmea.py` remain byte-identical to the
**Python files in SmartHomeServer commit**
`da75b65a0b369643ea16cf762d19d835975c3e21`. This does NOT mean they are identical
to the microcontroller's C firmware. [upstream.json](../upstream.json) records hashes;
[check_upstream.py](../scripts/check_upstream.py) checks hashes and original Git blobs.

**AGREED:** suggestions to improve these files are welcome. Prefer adapters or
subclasses for HA extensions; modifying the frozen source requires an explicit
decision, compatible protocol behavior and updated verification, not a silent hash
change. Receiver/controller firmware and bridge are separately built/deployed.

## One-way radio, refresh and health

**AGREED; VERIFIED in controller code:** show transmitted intent, not invented
feedback. Do not infer measured temperature, energy or a confirmed relay state.
Periodic normal power refresh applies to known boiler AND grow-light state;
Alarm/unknown state must not be refreshed. USB health probing is every **10 minutes**
(not the earlier 30-second proposal). Refresh interval is a separate option.

## Boiler schedule

**AGREED; historical screenshots, not freshly checked on HA:** reconcile Boiler
Power with its schedule while respecting Enabled. Schedule ON AND Enabled ON
requests Power ON; otherwise request OFF. Enabling alone does not switch hardware
in the bridge, so the HA automation also reacts to Enabled changes. Startup and
availability recovery were discussed; inspect the actual YAML before asserting
their exact trigger behavior. Manual Power commands may be replaced by the next
automation run. Do not treat the 05:00-22:00 repository example as the current live
schedule or confuse this interlock with the controller's temperature protections.

## Grow light: schedule, presence and illuminance

**AGREED; SCREENSHOT-confirmed editor configuration on 2026-09-16.** No exported
live YAML, runtime traces or physical acceptance were inspected on 2026-09-20.
Names below are UI labels, not guaranteed entity IDs. Keep the two presence
automations separate from the schedule automation unless a redesign is requested.

### Schedule automation: `Grow light schedule`

Triggers: schedule block started, schedule block ended, Home Assistant started.
No top-level condition. One ordered `Choose`, first matching branch only:

| Order | Conditions | Action |
| --- | --- | --- |
| 1 | Schedule OFF | Normal `light.turn_off` on Grow light Power: slow OFF |
| 2 | Schedule ON AND occupancy detected AND illuminance strictly below 70 lx | `button.press` on Grow light Fast off |
| 3 | Schedule ON | Normal `light.turn_on` on Grow light Power: slow ON |

No default action. The final screenshot still targeted device `Grow light (1)`
for branch 1 and the Power entity for branch 3; verify the first target resolves
only to the intended light if investigating execution. Device targeting alone is
not proof of a bug.

The user explicitly accepted checking existing presence at schedule start: if
someone is already present and it is dark, branch 2 sends Fast off. At schedule
end branch 1 takes priority, so the scheduled OFF command is always the slow one.

### Presence: `Grow light - Presence fast off`

- Trigger on occupancy detected OR illuminance crossing below 70 lx.
- All conditions required: schedule ON, occupancy detected, illuminance < 70 lx.
- Action: press Grow light Fast off. No added automation delay.
- The second trigger handles someone already present when it becomes dark.

### Absence: `Grow light - Absence fast on`

- Trigger on occupancy cleared.
- Condition: schedule ON only; **no illuminance condition**.
- Action: press Grow light Fast on. No added automation delay; sensor firmware
  may impose its own occupancy-clear timeout.

Boundary behavior: exactly 70 lx does not satisfy `< 70`. Unknown/unavailable
illuminance is not a numeric match. Rising to 70+ does not by itself send Fast on.
Do not add continuous Power-state enforcement: that would override manual actions.

**TO VERIFY / accepted limitations, not additional implemented features:**

- A HA-start trigger alone does not retry commands if Bridge is not ready yet.
- Unknown/unavailable sensor values at startup can bypass the dark/present branch.
- If the illuminance sensor sees the lamp, the lamp can keep the reading above 70.
- Do not add an unconditional power-unknown recovery trigger without considering
  Alarm and global Day/Night, which deliberately invalidate lamp power.

## Shared Day/Night and ASUS display

**AGREED; VERIFIED in local working-tree YAML, not freshly checked remotely:**

- DAY/NIGHT are global radio broadcasts for receivers implementing them, not only
  ASUS brightness settings. The night schedule activates Night and its end Day.
- `input_boolean.night_mode` is shared desired mode: ON = Night, OFF = Day.
  ASUS uses **15% at night, 100% during day**.
- Both manual Day/Night controls and schedule changes use the shared mode. Direct
  bridge button MQTT commands also synchronize it. Brightness must not follow
  only the schedule while ignoring buttons.
- Manual overrides last until the next schedule boundary. Helpers store the next
  boundary to preserve a valid override or catch up after an HA restart.
- Bridge reconnection reapplies mode; display reconnection restores brightness
  only. Do not reintroduce periodic schedule polling that erases manual overrides.
- Retain ASUS brightness requests, never retain radio command topics. Legacy
  button synchronization can cause an extra identical broadcast; use shared
  helper/scripts for a single command.
- Helpers/scripts live in a HA package; the four automations belong in
  `automations.yaml` with IDs for UI editing, not inside the package.

Sources: [ASUS notes](../extras/README.md), [package](../extras/asus-brightness/day_night.yaml),
[automations](../extras/asus-brightness/day_night_automations.yaml).
These migration files are included with the project documentation in the combined
PR change set; see HANDOFF. Publication does not deploy them to HA or ASUS.

**AGREED / historical ASUS setup:** Firefox fullscreen kiosk at login, no screen
blanking or lock, persistent non-private profile, power button performs shutdown.
Persistent login is not a guarantee after session revocation. Kiosk/dashboard
visibility is not real authorization; never claim it prevents access to other HA
resources. The user's request for strict dashboard-only access remains separate.

## Zigbee

**REPORTED:** ZBDongle-P (CC2652P) connected.
**PROPOSED, not yet approved for installation in this conversation:** Zigbee2MQTT
using the existing Mosquitto broker, `adapter: zstack`, a stable serial path and
a USB extension. ZHA is an alternative; the same dongle cannot be owned by both.
Do not confuse ZBDongle-P with ZBDongle-E or the 433 MHz controller. No verified
firmware update, channel selection, Zigbee installation or pairing is recorded.

## Release and documentation discipline

- Tests first; report skips, then commit/push only when requested. A passing host
  test does not establish safe physical behavior or target compilation.
- Do not merge PRs, flash or deploy just to make the handoff appear complete.
- English UI names/documentation; preserve legacy IDs until an explicit migration.
- Store no passwords/tokens/keys in these files. Access locations are sufficient.
- Historical chat has incorrect/intermediate advice. Prefer dated code evidence,
  the latest user decision and live validation over repeating an old assertion.
