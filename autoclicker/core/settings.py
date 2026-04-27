import json
import os
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "button": "Left",
    "type": "Single",
    "click_behaviour": "single",
    "interval_h": 0,
    "interval_m": 0,
    "interval_s": 0,
    "interval_ms": 100,
    "location_mode": "Follow cursor",
    "x": 0,
    "y": 0,
    "random_offset_enabled": False,
    "random_offset_px": 5,
    "repeat_mode": "Infinite",
    "repeat_count": 10,
    "timer_mode": "None",
    "timer_seconds": 10,
    "start_delay": 3,
    "tray_on_close": True,
    "hotkey_start": "F6",
    "hotkey_stop": "F7",
    "recording": [],
}


class SettingsStore:
    def __init__(self) -> None:
        appdata = os.getenv("APPDATA", os.path.expanduser("~"))
        self.config_dir = os.path.join(appdata, "AutoClicker")
        self.config_path = os.path.join(self.config_dir, "autoclicker_config.json")

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return DEFAULT_CONFIG.copy()
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            if "click_behaviour" not in merged:
                legacy = str(merged.get("type", "Single")).strip().lower()
                if legacy in {"single", "double", "triple"}:
                    merged["click_behaviour"] = legacy
                else:
                    merged["click_behaviour"] = "single"
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save(self, config: Dict[str, Any]) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        payload = DEFAULT_CONFIG.copy()
        payload.update(config)
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
