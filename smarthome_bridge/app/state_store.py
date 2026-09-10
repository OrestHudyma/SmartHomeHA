"""Persist interlocks and discovery ownership, never restore power-on commands."""
import json
import os
from pathlib import Path
import tempfile


class StateStore:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "enabled": {}, "discovery_topics": []}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if (data.get("version") != 1 or not isinstance(data.get("enabled"), dict)
                        or any(type(v) is not bool for v in data["enabled"].values())
                        or not isinstance(data.get("discovery_topics"), list)
                        or any(not isinstance(v, str) for v in data["discovery_topics"])):
                    raise ValueError("Invalid state schema")
                self.data = data
            except (ValueError, AttributeError) as exc:
                # Never silently re-enable a boiler after losing its interlock.
                raise ValueError("Stored state is invalid; restore a backup before starting") from exc

    def enabled(self, key):
        return self.data["enabled"].get(key, True)

    def set_enabled(self, key, value):
        updated = dict(self.data, enabled=dict(self.data["enabled"], **{key: value}))
        self._save(updated)

    def set_discovery_topics(self, topics):
        self._save(dict(self.data, discovery_topics=sorted(topics)))

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix="state-", suffix=".tmp", delete=False) as file:
                name = file.name
                json.dump(data, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.path)
            self.data = data
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
