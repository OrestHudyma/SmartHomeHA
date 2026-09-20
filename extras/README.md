# ASUS wall display

These files record the separately deployed ASUS Eee PC 901 setup on Lubuntu
18.04. They are not part of the bridge container and are not applied by an app
update. No passwords, browser sessions or MQTT credentials are included.

## Kiosk

`asus-kiosk/` contains the deployed Firefox launcher, autostart entries, profile
preferences, LightDM automatic-login configuration and user power settings.
The examples are specific to user `orest`, Firefox profile
`xoxdy9jn.default-release`, and `http://192.168.0.127/wall-panel/0`.
Review and adapt all paths before using them on another machine.

The original setup staged these files in `/home/orest/ha-kiosk-setup`, then ran
`install-user.sh` in the user's graphical session. It saves a private backup under
`~/.local/share/ha-kiosk-backup-*` before replacing user settings. The LightDM file
is installed separately to `/etc/lightdm/lightdm.conf.d/90-ha-dashboard.conf`.
The deployed power-button setting is:

```sh
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/power-button-action -s 3
```

This makes a short power-button press shut down the laptop. Screen blanking, DPMS
and automatic locking are disabled. Firefox uses its existing, non-private
profile; select **Keep me logged in** when logging in to HA. Revoked sessions or
authentication changes can still require a new login. Kiosk mode is not an access
control boundary. Automatic OS login and an unlocked display require physical
trust; do not use an administrator HA account for a shared display.

## Day/night backlight

`asus-brightness/brightness.py` runs on the ASUS with Python 3.6 and the distribution
package `python3-paho-mqtt` (deployed version 1.3.1). It subscribes to retained MQTT
commands and controls the physical `intel_backlight`, not a software overlay.

Installed files:

- `brightness.py`: `/opt/asus-brightness/brightness.py`
- `asus-brightness.service`: `/etc/systemd/system/asus-brightness.service`
- Private credentials: `/etc/asus-brightness/mqtt.json` (root-owned, mode 600,
  parent directory mode 700)
- `day_night.yaml`: `/config/packages/day_night.yaml` on Home Assistant
- `day_night_automations.yaml`: merge its four entries into `/config/automations.yaml`

The service runs as root to write the backlight and restricts writable system
paths. Its `ReadWritePaths` matches this ASUS's resolved Intel backlight path;
check `readlink -f /sys/class/backlight/intel_backlight` on other hardware.
Provision a dedicated MQTT user, not Home Assistant's internal integration
credentials. The private JSON schema is:

```json
{"host": "192.168.0.127", "port": 1883, "username": "asus_display", "password": "REPLACE_LOCALLY"}
```

Do not commit that file. This setup uses plain MQTT on the trusted LAN; do not
expose the broker directly to the internet.

The HA configuration loads the shared-mode package (merge into an existing
`homeassistant` section if present):

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Keep the existing `automation: !include automations.yaml` entry. The four automations
belong directly in that file, with their IDs preserved, so HA's visual editor can
edit them. Do not replace unrelated automations or add a separate include for these
entries. The package contains only helpers and scripts. When migrating from the
previous package, remove its `automation` section after moving all four entries.
Remove the old
`automation asus_display: !include asus_display.yaml` entry and the old Global
Day/Night schedule automation, which sent broadcasts directly. Validate HA
configuration before restarting. The bridge container needs no changes.

`input_boolean.night_mode` is now the shared desired mode: **on = Night / 15%**,
**off = Day / 100%**. The schedule only changes this helper on real on/off edges.
Use the helper toggle or `script.day_mode` / `script.night_mode` on dashboards.
`asus-brightness/day_night_card.yaml` is a ready-to-paste dashboard card.
Manual changes last until the next schedule boundary. The saved next boundary
allows HA startup to preserve an unexpired override or catch up after a missed
boundary. The first startup initializes the helper from the schedule. Unknown
schedule states are ignored (startup waits up to one minute).

Changing the helper sets ASUS brightness and sends the matching broadcast through
the existing bridge button. Bridge reconnection reapplies the desired mode;
display reconnection restores only brightness. No five-minute schedule polling
overwrites manual mode. If the bridge is unavailable, ASUS still changes and the
broadcast is retried on bridge reconnection. The helper represents intent, not
confirmation from one-way radio devices.

Existing bridge Day/Night buttons also synchronize the helper through their MQTT
command topics. A legacy button that changes mode can cause one extra identical
broadcast when the shared mode is applied; this is idempotent, not a loop. Prefer
the shared toggle/scripts for a single command. The deployment uses bridge ID
`smarthome`, global device ID `1`, and the existing entity IDs in the YAML;
adapt these when installing elsewhere. Global command topics must not be retained.

Retained brightness commands restore the last request after a display-service
restart. The previous `asus_display.yaml` example is replaced by this package.

MQTT topics under `wallpanel/asus/brightness`:

- `/set`: integer 1 through 100; zero and malformed commands are rejected.
- `/state`: retained JSON with `requested_percent`, `raw` and `maximum`.
- `/availability`: retained `online`/`offline`, with an offline last will.

On this ASUS, maximum raw brightness is 796875; day uses 796875 and night 119531.
The service is enabled at boot. Inspect it without changing brightness:

```sh
systemctl status asus-brightness
journalctl -u asus-brightness -n 30 --no-pager
cat /sys/class/backlight/intel_backlight/brightness
```

Tests (no hardware writes or MQTT connection):

```sh
python -m unittest discover -s extras/asus-brightness -p 'test_*.py' -v
```
