import json
import os
import random
import threading
import time
from datetime import datetime

import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


BUTTON_MAP = {"Left": "left", "Right": "right", "Middle": "middle"}
CLICK_BEHAVIOUR_TO_COUNT = {
    "single": 1,
    "double": 2,
    "triple": 3,
}


def _apply_random_offset(x: int, y: int, config: dict) -> tuple[int, int]:
    """Apply random offset to x, y if random_offset_enabled is True."""
    if config.get("random_offset_enabled", False):
        offset_px = int(config.get("random_offset_px", 5))
        x += random.randint(-offset_px, offset_px)
        y += random.randint(-offset_px, offset_px)
    return x, y


class ClickerThread(QThread):
    state_changed = pyqtSignal(str)
    click_count_changed = pyqtSignal(int)
    last_click_time_changed = pyqtSignal(str)
    finished_with_reason = pyqtSignal(str)

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._stop_event = threading.Event()
        self._session_clicks = 0

    def stop(self) -> None:
        self._stop_event.set()

    def _do_click(self) -> None:
        button = BUTTON_MAP.get(self.config["button"], "left")
        click_behaviour = str(
            self.config.get("click_behaviour", self.config.get("type", "Single"))
        ).strip().lower()
        click_count = CLICK_BEHAVIOUR_TO_COUNT.get(click_behaviour, 1)
        sub_click_interval = 0.03 if click_count == 3 else 0

        if self.config["location_mode"] == "Fixed XY":
            x = int(self.config["x"])
            y = int(self.config["y"])
            x, y = _apply_random_offset(x, y, self.config)
            pyautogui.click(
                x=x,
                y=y,
                clicks=click_count,
                interval=sub_click_interval,
                button=button,
            )
            return

        pos = pyautogui.position()
        x, y = pos.x, pos.y
        x, y = _apply_random_offset(x, y, self.config)
        pyautogui.click(
            x=x,
            y=y,
            clicks=click_count,
            interval=sub_click_interval,
            button=button,
        )

    def run(self) -> None:
        self._stop_event.clear()
        self.state_changed.emit("Running")

        interval_h = int(self.config.get("interval_h", 0))
        interval_m = int(self.config.get("interval_m", 0))
        interval_s = int(self.config.get("interval_s", 0))
        interval_ms_val = int(self.config.get("interval_ms", 100))
        interval_seconds = max(0.001, (interval_h * 3600 + interval_m * 60 + interval_s) + interval_ms_val / 1000.0)

        repeat_mode = self.config["repeat_mode"]
        repeat_count = int(self.config["repeat_count"])
        timer_mode = self.config["timer_mode"]
        timer_seconds = float(self.config["timer_seconds"])

        start_time = time.monotonic()
        executed = 0

        while not self._stop_event.is_set():
            if repeat_mode == "Fixed count" and executed >= repeat_count:
                self.finished_with_reason.emit("Stopped")
                return

            if timer_mode == "Stop after N seconds":
                elapsed = time.monotonic() - start_time
                if elapsed >= timer_seconds:
                    self.finished_with_reason.emit("Stopped")
                    return

            try:
                self._do_click()
            except Exception as exc:
                print(f"[AutoClicker] click error: {exc}")

            executed += 1
            self._session_clicks += 1
            self.click_count_changed.emit(self._session_clicks)
            self.last_click_time_changed.emit(datetime.now().strftime("%H:%M:%S"))

            if self._stop_event.wait(interval_seconds):
                break

        self.finished_with_reason.emit("Stopped")
        ## thanku 