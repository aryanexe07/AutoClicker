import threading
import time
from datetime import datetime

import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


BUTTON_MAP = {"Left": "left", "Right": "right", "Middle": "middle"}


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
        click_count = 2 if self.config["type"] == "Double" else 1

        if self.config["location_mode"] == "Fixed XY":
            x = int(self.config["x"])
            y = int(self.config["y"])
            pyautogui.click(x=x, y=y, clicks=click_count, interval=0, button=button)
            return

        pyautogui.click(clicks=click_count, interval=0, button=button)

    def run(self) -> None:
        self._stop_event.clear()
        self.state_changed.emit("Running")

        interval_seconds = max(0.001, float(self.config["interval_ms"]) / 1000.0)
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