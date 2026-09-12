#!/bin/sh
set -eu
exec 9>/home/orest/.cache/ha-dashboard.lock
flock -n 9 || exit 0
xset s off
xset s noblank
xset -dpms
# Wait for networking and Home Assistant before opening the dashboard.
until wget -q -O /dev/null --timeout=5 --tries=1 http://192.168.0.127/; do
    sleep 5
done
exec /usr/bin/firefox --no-remote --profile /home/orest/.mozilla/firefox/xoxdy9jn.default-release --kiosk http://192.168.0.127/wall-panel/0
