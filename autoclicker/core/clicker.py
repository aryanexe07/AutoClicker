import json
import os
import random
import threading
import time
from datetime import datetime

import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from core.app_logger import get_logger
except ModuleNotFoundError:  # pragma: no cover - package import path
    from .app_logger import get_logger

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

    def __init__(self, config: dict, multi_sequence: list = None) -> None:
        super().__init__()
        self.config = config
        self.multi_sequence = multi_sequence or []
        self._stop_event = threading.Event()
        self._session_clicks = 0
        self._multi_mode = bool(self.config.get("multi_mode", False))
        self._current_multi_index = 0
        self._multi_pass_count = 0
        self._logger = get_logger()

    def stop(self) -> None:
        self._stop_event.set()

    def _do_click_at(self, x: int, y: int) -> None:
        """Perform a single click at the given coordinates."""
        button = BUTTON_MAP.get(self.config["button"], "left")
        click_behaviour = str(
            self.config.get("click_behaviour", self.config.get("type", "Single"))
        ).strip().lower()
        click_count = CLICK_BEHAVIOUR_TO_COUNT.get(click_behaviour, 1)
        sub_click_interval = 0.03 if click_count == 3 else 0
        x, y = _apply_random_offset(x, y, self.config)
        pyautogui.click(
            x=x, y=y,
            clicks=click_count,
            interval=sub_click_interval,
            button=button,
        )

    def _do_click(self) -> None:
        """Perform a click (used in normal mode vs multi-point mode)."""
        if self._multi_mode and self.multi_sequence:
            # Iterate through multi-point sequence
            point = self.multi_sequence[self._current_multi_index]
            px = int(point["x"])
            py = int(point["y"])
            px, py = _apply_random_offset(px, py, self.config)
            delay_after = float(point.get("delay_ms", 100)) / 1000.0
            
            button = BUTTON_MAP.get(self.config["button"], "left")
            click_bhv = str(
                self.config.get("click_behaviour", self.config.get("type", "Single"))
            ).strip().lower()
            click_count = CLICK_BEHAVIOUR_TO_COUNT.get(click_bhv, 1)
            sub_int = 0.03 if click_count == 3 else 0
            
            pyautogui.click(x=px, y=py, clicks=click_count, interval=sub_int, button=button)
            
            # Move to next point
            self._current_multi_index += 1
            if self._current_multi_index >= len(self.multi_sequence):
                self._current_multi_index = 0
                self._multi_pass_count += 1
                repeat_mode = self.config.get("repeat_mode", "Infinite")
                if repeat_mode == "Fixed count":
                    repeat_count = int(self.config.get("repeat_count", 10))
                    if self._multi_pass_count >= repeat_count:
                        self.finished_with_reason.emit("Stopped")
                        return
            # Return the delay for multi-point
            time.sleep(delay_after)
        else:
            # Normal (legacy) single click mode
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
                    x=x, y=y,
                    clicks=click_count, interval=sub_click_interval,
                    button=button,
                )
                return

            pos = pyautogui.position()
            x, y = pos.x, pos.y
            x, y = _apply_random_offset(x, y, self.config)
            pyautogui.click(
                x=x, y=y,
                clicks=click_count, interval=sub_click_interval,
                button=button,
            )

    def run(self) -> None:
        self._stop_event.clear()
        self.state_changed.emit("Running")

        interval_h = int(self.config.get("interval_h", 0))
        interval_m = int(self.config.get("interval_m", 0))
        interval_s = int(self.config.get("interval_s", 0))
        interval_ms_val = int(self.config.get("interval_ms", 100))
        total_interval_ms = (interval_h * 3600000 + interval_m * 60000 +
                             interval_s * 1000 + interval_ms_val)
        interval_seconds = max(0.001, total_interval_ms / 1000.0)

        repeat_mode = self.config.get("repeat_mode", "Infinite")
        repeat_count = int(self.config.get("repeat_count", 10))
        timer_mode = self.config.get("timer_mode", "None")
        timer_seconds = float(self.config.get("timer_seconds", 10))

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
                if self._multi_mode and self.multi_sequence:
                    self._do_click()
                else:
                    self._do_click()
            except Exception as exc:
                self._logger.exception("Click execution error: %s", exc)

            executed += 1
            self._session_clicks += 1
            self.click_count_changed.emit(self._session_clicks)
            self.last_click_time_changed.emit(datetime.now().strftime("%H:%M:%S"))

            # In multi-point mode, delay is handled per-point; use interval only between full passes
            if self._multi_mode and self.multi_sequence:
                if self._stop_event.wait(interval_seconds):
                    break
                continue

            if self._stop_event.wait(interval_seconds):
                break

        self.finished_with_reason.emit("Stopped")