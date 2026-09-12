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
- `asus_display.yaml`: `/config/asus_display.yaml` on Home Assistant

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

The HA configuration includes the automation with a separate top-level key:

```yaml
automation asus_display: !include asus_display.yaml
```

Keep the existing `automation: !include automations.yaml` entry. Validate HA
configuration before loading changes. Do not add the same automation twice.

The automation follows `schedule.night_mode`: **on = 15%**, **off = 100%**.
It resynchronizes at HA start, MQTT availability events and every five minutes.
Unknown/unavailable schedule states do not publish a new value. Retained commands
restore the last requested brightness after a display-service restart. This is
independent of the broadcast Day/Night commands sent by SmartHome Bridge.

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
python -m unittest discover -s extras/asus-brightness -p test_brightness.py -v
```
