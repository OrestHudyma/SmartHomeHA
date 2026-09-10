#!/bin/sh
set -eu
exec python -u /app/main.py --options /data/options.json --state /data/state.json
