# Development

Python 3.10+ for local tests; the app runs pinned Python 3.13 in its container.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/check_upstream.py
python -m unittest discover -s smarthome_bridge -p test.py -v
```

On Windows activate `.venv\Scripts\Activate.ps1`, or call its python.exe directly.
No physical USB hardware is accessed by these tests. The retained upstream tests
use mocks, the bridge tests cover behavior and faults, and the Linux end-to-end
test opens a pseudo-terminal served by a serial-controller emulator.

## MQTT integration tests

Start an isolated Mosquitto 2 broker on localhost and set `MQTT_TEST_PORT` to its
port. `MQTT_TEST_HOST` defaults to 127.0.0.1. CI runs all integration tests and the
real Python entrypoint with a pseudo-terminal, including shutdown via SIGTERM.
Without this environment variable, only broker integration tests are skipped.

```sh
MQTT_TEST_PORT=18884 python -m unittest discover -s smarthome_bridge -p test.py -v
docker build --build-arg BUILD_ARCH=amd64 -t smarthome-bridge:test smarthome_bridge
docker buildx build --platform linux/arm64 --build-arg BUILD_ARCH=aarch64 smarthome_bridge
```

The Dockerfile supports Supervisor source builds. It does not require legacy
`build.yaml` or implicit `BUILD_FROM`. No SSH, API token or physical switching is
part of CI.

## Add a new device type

Implement an adapter in `smarthome_bridge/app/devices/` based on `Adapter`, with a
factory, explicit actions and discovery definitions. Register it in `REGISTRY`
and add its name to the `devices.type` schema in the app config. Extend the
controller/discovery for any new entity domains or state behavior. Supply command,
failure and discovery tests, update documentation and increment the app version.
Existing lamp instances only require options changes, not Python changes.

Keep `periphery.py` and `nmea.py` untouched. `upstream.json` records source hashes;
`scripts/check_upstream.py` compares raw bytes with both those hashes and the
original Git blobs. CI requires full Git history. Git attributes preserve LF bytes
for the upstream files on Windows as well as Linux.

## Releases

Run tests, source-integrity check and both container builds. Update matching
versions in `config.yaml`, `app/discovery.py`, Dockerfile build-arg default and
CHANGELOG. Tag the commit and publish release notes. The add-on's source-build
workflow becomes available after the repository update is refreshed in HA.
Keep `stage: experimental` until physical-device acceptance is complete.
