import json
import os
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "button": "Left",
    "type": "Single",
    "interval_ms": 100,
    "location_mode": "Follow cursor",
    "x": 0,
    "y": 0,
    "repeat_mode": "Infinite",
    "repeat_count": 10,
    "timer_mode": "None",
    "timer_seconds": 10,
    "start_delay": 3,
    "hotkey_start": "F6",
    "hotkey_stop": "F7",
}


class SettingsStore:
    def __init__(self) -> None:
        appdata = os.getenv("APPDATA", os.path.expanduser("~"))
        self.config_dir = os.path.join(appdata, "AutoClicker")
        self.config_path = os.path.join(self.config_dir, "config.json")

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return DEFAULT_CONFIG.copy()
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save(self, config: Dict[str, Any]) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        payload = DEFAULT_CONFIG.copy()
        payload.update(config)
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
