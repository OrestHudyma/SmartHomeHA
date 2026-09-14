"""Home Assistant MQTT discovery, keyed by identity rather than display names."""
from devices.registry import REGISTRY

VERSION = "0.1.3"


def discovery_messages(settings):
    result = {}
    prefix = settings.prefix
    bridge_availability = {"topic": f"{prefix}/availability"}
    hardware_availability = {"topic": f"{prefix}/hardware"}
    for config in settings.devices:
        adapter = REGISTRY[config.type]
        base = f"{prefix}/{config.key}"
        device = {"identifiers": [f"{settings.bridge_id}_{config.key}"],
                  "name": config.name, "manufacturer": "OrestHudyma",
                  "model": config.type, "sw_version": VERSION}

        def add(domain, entity, name, extra):
            uid = f"{settings.bridge_id}_{config.key}_{entity}"
            result[f"{settings.discovery_prefix}/{domain}/{uid}/config"] = {
                "unique_id": uid, "name": name, "device": device,
                "origin": {"name": "SmartHome Bridge", "sw_version": VERSION},
                "availability": [bridge_availability, hardware_availability],
                "availability_mode": "all", **extra,
            }

        if adapter.power_domain:
            add(adapter.power_domain, "power", "Power", {
                "command_topic": f"{base}/power/set", "state_topic": f"{base}/power/state",
                "payload_on": "ON", "payload_off": "OFF", "optimistic": False,
                "retain": False, "qos": 1, "json_attributes_topic": f"{base}/attributes",
            })
        if config.type == "boiler":
            add("switch", "enabled", "Enabled", {
                "command_topic": f"{base}/enabled/set", "state_topic": f"{base}/enabled/state",
                "payload_on": "ON", "payload_off": "OFF", "optimistic": False,
                "retain": False, "qos": 1,
            })
        for action, (name, _) in adapter.buttons.items():
            add("button", action, name, {
                "command_topic": f"{base}/{action}/set", "payload_press": "PRESS",
                "retain": False, "qos": 1,
            })
        add("sensor", "result", "Command result", {
            "state_topic": f"{base}/result", "entity_category": "diagnostic",
            "availability": [bridge_availability],
        })
    result[f"{settings.discovery_prefix}/binary_sensor/{settings.bridge_id}_controller/config"] = {
        "unique_id": f"{settings.bridge_id}_controller", "name": "USB controller",
        "device_class": "connectivity", "entity_category": "diagnostic",
        "state_topic": f"{prefix}/hardware", "payload_on": "online", "payload_off": "offline",
        "availability": [bridge_availability],
        "device": {"identifiers": [settings.bridge_id], "name": "SmartHome Bridge"},
        "origin": {"name": "SmartHome Bridge", "sw_version": VERSION},
    }
    return result
