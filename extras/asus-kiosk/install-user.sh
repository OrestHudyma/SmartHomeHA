#!/bin/sh
set -eu
cd /home/orest/ha-kiosk-setup
backup=/home/orest/.local/share/ha-kiosk-backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup" /home/orest/.config/autostart /home/orest/.local/bin /home/orest/.cache
chmod 700 "$backup"
cp -a /home/orest/.config/xfce4 "$backup/"
cp -a /home/orest/.config/lxsession "$backup/"
for f in /home/orest/.config/autostart/ha-dashboard.desktop /home/orest/.config/autostart/light-locker.desktop /home/orest/.local/bin/ha-dashboard.sh /home/orest/.mozilla/firefox/xoxdy9jn.default-release/user.js; do
    if [ -f "$f" ]; then cp -a "$f" "$backup/"; fi
done
install -m 755 ha-dashboard.sh /home/orest/.local/bin/ha-dashboard.sh
install -m 644 ha-dashboard.desktop light-locker.desktop /home/orest/.config/autostart/
install -m 600 user.js /home/orest/.mozilla/firefox/xoxdy9jn.default-release/user.js
set_prop() {
    if xfconf-query -c xfce4-power-manager -p "/xfce4-power-manager/$1" >/dev/null 2>&1; then
        xfconf-query -c xfce4-power-manager -p "/xfce4-power-manager/$1" -s "$3"
    else
        xfconf-query -c xfce4-power-manager -p "/xfce4-power-manager/$1" --create -t "$2" -s "$3"
    fi
}
set_prop presentation-mode bool true
set_prop dpms-enabled bool false
set_prop lock-screen-suspend-hibernate bool false
for source in ac battery; do
    set_prop "blank-on-$source" int 0
    set_prop "dpms-on-$source-sleep" uint 0
    set_prop "dpms-on-$source-off" uint 0
    set_prop "inactivity-on-$source" uint 14
    set_prop "brightness-on-$source" uint 9
done
pkill -u orest -x light-locker || true
xset s off
xset s noblank
xset -dpms
printf 'Backup: %s\n' "$backup"
