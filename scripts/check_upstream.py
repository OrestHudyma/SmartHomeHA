"""Compare canonical source bytes with the recorded upstream commit."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "da75b65a0b369643ea16cf762d19d835975c3e21"


def verify():
    manifest = json.loads((ROOT / "upstream.json").read_text())
    if manifest["commit"] != BASE:
        raise AssertionError("Unexpected upstream commit")
    for name, expected in manifest["sha256"].items():
        upstream = subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=ROOT)
        actual = (ROOT / "smarthome_bridge" / "app" / name).read_bytes()
        if actual != upstream or hashlib.sha256(actual).hexdigest() != expected:
            raise AssertionError(f"Upstream file changed: {name}")
    print("periphery.py and nmea.py match the upstream Git blobs")


if __name__ == "__main__":
    verify()
