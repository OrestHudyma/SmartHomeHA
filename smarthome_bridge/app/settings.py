"""Validated add-on options; no Home Assistant imports in the runtime."""
from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class DeviceConfig:
    type: str
    id: str
    name: str

    @property
    def key(self):
        return f"{self.type}_{self.id}"


@dataclass(frozen=True)
class Settings:
    serial_port: str
    devices: tuple
    bridge_id: str = "smarthome"
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = field(default="", repr=False)
    mqtt_tls: bool = False
    discovery_prefix: str = "homeassistant"
    ha_status_topic: str = "homeassistant/status"
    refresh_seconds: int = 3600
    log_level: str = "INFO"

    @property
    def prefix(self):
        return f"smarthome/{self.bridge_id}"

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data):
        from devices.registry import REGISTRY
        if not isinstance(data, dict):
            raise ValueError("Options must be an object")
        allowed = set(cls.__dataclass_fields__)
        if set(data) - allowed:
            raise ValueError("Unknown configuration keys")
        port = data.get("serial_port", "")
        if not isinstance(port, str) or not port.startswith("/dev/") or ".." in port.split("/"):
            raise ValueError("serial_port must be a /dev/ path; prefer /dev/serial/by-id/...")
        items = data.get("devices")
        if not isinstance(items, list) or not items:
            raise ValueError("Configure at least one device")
        devices, seen, counts = [], set(), {}
        for item in items:
            if not isinstance(item, dict) or set(item) != {"type", "id", "name"}:
                raise ValueError("Each device requires type, id and name")
            kind, ident, name = item["type"], item["id"], item["name"]
            if not isinstance(kind, str) or kind not in REGISTRY:
                raise ValueError("Unknown device type")
            if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", ident):
                raise ValueError("Device id must be a short identifier string")
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                raise ValueError("Device name must contain 1..100 characters")
            adapter = REGISTRY[kind]
            adapter.validate_id(ident)
            device = DeviceConfig(kind, ident, name)
            counts[kind] = counts.get(kind, 0) + 1
            if device.key in seen or (adapter.singleton and counts[kind] > 1):
                raise ValueError("Duplicate device or multiple unaddressed devices")
            seen.add(device.key)
            devices.append(device)
        values = dict(data, devices=tuple(devices))
        result = cls(**values)
        if not isinstance(result.bridge_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", result.bridge_id):
            raise ValueError("Invalid bridge_id")
        for key, low, high in (("mqtt_port", 1, 65535), ("refresh_seconds", 60, 3600)):
            value = getattr(result, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} must be an integer in {low}..{high}")
        for key in ("mqtt_host", "mqtt_username", "mqtt_password"):
            if not isinstance(getattr(result, key), str):
                raise ValueError(f"{key} must be a string")
        if type(result.mqtt_tls) is not bool:
            raise ValueError("mqtt_tls must be boolean")
        for key in ("discovery_prefix", "ha_status_topic"):
            value = getattr(result, key)
            if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_/-]{1,128}", value):
                raise ValueError(f"Invalid {key}")
        if result.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError("Invalid log_level")
        return result


def mqtt_credentials(settings, token=None):
    """Explicit broker or Supervisor MQTT service, never log credentials."""
    if settings.mqtt_host:
        return settings.mqtt_host, settings.mqtt_port, settings.mqtt_username, settings.mqtt_password
    if not token:
        raise ValueError("Configure mqtt_host or provide Supervisor MQTT service access")
    request = Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=10) as response:
        service = json.load(response)
    if service.get("result") != "ok":
        raise ValueError("Supervisor MQTT service is unavailable")
    data = service["data"]
    return data["host"], int(data["port"]), data["username"], data["password"]
