import json
import os
import threading
import time
from typing import List, Optional

from pynput import keyboard, mouse
from PyQt6.QtCore import QMetaObject, QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.clicker import ClickerThread
from core.app_logger import get_logger
from core.settings import SettingsStore
from ui.hotkey_dialog import HotkeyDialog


CLICK_BEHAVIOUR_LABEL_TO_VALUE = {
    "Single": "single",
    "Double": "double",
    "Triple": "triple",
}
CLICK_BEHAVIOUR_VALUE_TO_LABEL = {value: label for label, value in CLICK_BEHAVIOUR_LABEL_TO_VALUE.items()}


class HotkeyBridge(QObject):
    toggle_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    @pyqtSlot()
    def emit_toggle(self) -> None:
        self.toggle_requested.emit()

    @pyqtSlot()
    def emit_stop(self) -> None:
        self.stop_requested.emit()


class GlobalHotkeyListener(threading.Thread):
    def __init__(self, bridge: HotkeyBridge, start_hotkey: str, stop_hotkey: str) -> None:
        super().__init__(daemon=True)
        self.bridge = bridge
        self._logger = get_logger()
        self._hotkey_lock = threading.Lock()
        self._start_hotkey = start_hotkey
        self._stop_hotkey = stop_hotkey
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: set[str] = set()
        self._stop_event = threading.Event()

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        cleaned = name.strip().lower()
        aliases = {
            "control": "ctrl",
            "lcontrol": "ctrl",
            "rcontrol": "ctrl",
            "alt_l": "alt",
            "alt_r": "alt",
            "shift_l": "shift",
            "shift_r": "shift",
            "windows": "cmd",
            "win": "cmd",
            "super": "cmd",
        }
        return aliases.get(cleaned, cleaned)

    @classmethod
    def _parse_hotkey(cls, hotkey: str) -> set[str]:
        parts = [part for part in hotkey.lower().replace(" ", "").split("+") if part]
        return {cls._normalize_key_name(part) for part in parts}

    @classmethod
    def _key_to_name(cls, key) -> Optional[str]:
        if isinstance(key, keyboard.KeyCode) and key.char:
            return cls._normalize_key_name(key.char)
        if isinstance(key, keyboard.Key):
            return cls._normalize_key_name(key.name or "")
        return None

    def update_hotkeys(self, start_hotkey: str, stop_hotkey: str) -> None:
        with self._hotkey_lock:
            self._start_hotkey = start_hotkey
            self._stop_hotkey = stop_hotkey

    def run(self) -> None:
        try:
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
            self._listener.join()
        except Exception as exc:
            self._logger.exception("Hotkey listener crashed: %s", exc)
        finally:
            self._listener = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._listener is not None:
            self._listener.stop()

    def _on_press(self, key) -> None:
        if self._stop_event.is_set():
            return
        key_name = self._key_to_name(key)
        if not key_name:
            return
        self._pressed_keys.add(key_name)
        with self._hotkey_lock:
            start_hotkey = self._parse_hotkey(self._start_hotkey)
            stop_hotkey = self._parse_hotkey(self._stop_hotkey)
        if stop_hotkey and stop_hotkey.issubset(self._pressed_keys):
            self._on_stop()
            return
        if start_hotkey and start_hotkey.issubset(self._pressed_keys):
            self._on_toggle()

    def _on_release(self, key) -> None:
        key_name = self._key_to_name(key)
        if key_name:
            self._pressed_keys.discard(key_name)

    def _on_toggle(self) -> None:
        QMetaObject.invokeMethod(self.bridge, "emit_toggle", Qt.ConnectionType.QueuedConnection)

    def _on_stop(self) -> None:
        QMetaObject.invokeMethod(self.bridge, "emit_stop", Qt.ConnectionType.QueuedConnection)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Clicker")
        self.setFixedSize(480, 720)

        self.settings_store = SettingsStore()
        self.config = self.settings_store.load()

        self.clicker_thread: Optional[ClickerThread] = None
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.remaining_delay = 0
        self.session_clicks = 0
        self.hotkey_listener: Optional[GlobalHotkeyListener] = None
        self.hotkey_watchdog = QTimer(self)
        self.hotkey_watchdog.setInterval(5000)
        self.hotkey_watchdog.timeout.connect(self._ensure_hotkey_listener_alive)
        self._logger = get_logger()

        # Recording state
        self.recording = self.config.get("recording", [])  # list of {x, y, delay_ms}
        self.is_recording = False
        self.record_start_time = 0
        self.recorded_clicks: List[dict] = []
        self.record_mouse_listener: Optional[mouse.Listener] = None

        # Playback state
        self.playback_thread: Optional[threading.Thread] = None
        self.playback_stop_event = threading.Event()

        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.toggle_requested.connect(self.toggle_start_stop)
        self.hotkey_bridge.stop_requested.connect(self.emergency_stop)

        self._build_ui()
        self._load_config_to_ui()
        self._update_location_controls()
        self._update_repeat_controls()
        self._update_timer_controls()
        self._update_status("Idle")
        self._update_recording_ui()
        self._start_hotkey_listener()
        self.hotkey_watchdog.start()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #F7F8FC;
                color: #1A1D23;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E2E5EE;
                border-radius: 8px;
                margin-top: 10px;
                padding: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                top: 2px;
                color: #6B7280;
                font-weight: 600;
            }
            QLabel {
                color: #1A1D23;
            }
            QComboBox, QSpinBox, QPushButton, QLineEdit {
                border: 1px solid #D5DAE8;
                border-radius: 6px;
                padding: 6px 8px;
                background-color: #FFFFFF;
            }
            QPushButton {
                background-color: #4F7EF7;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3D69DC;
            }
            QPushButton:pressed {
                background-color: #2F54C7;
            }
            QPushButton#recordButton {
                background-color: #EF4444;
            }
            QPushButton#recordButton:hover {
                background-color: #DC2626;
            }
            QPushButton#recordButton.recording {
                background-color: #EF4444;
                animation: pulse 1s infinite;
            }
            QPushButton#playButton {
                background-color: #10B981;
            }
            QPushButton#playButton:hover {
                background-color: #059669;
            }
            QPushButton#clearButton {
                background-color: #6B7280;
            }
            QPushButton#clearButton:hover {
                background-color: #4B5563;
            }
            QPushButton:disabled {
                background-color: #D5DAE8;
                color: #9CA3AF;
            }
            QToolBar {
                border: none;
                spacing: 8px;
                padding: 8px;
                background-color: #F7F8FC;
            }
            QStatusBar {
                border-top: 1px solid #E2E5EE;
                background-color: #FFFFFF;
            }
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #D5DAE8;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #F3F4F6;
            }
            QListWidget::item:last-child {
                border-bottom: none;
            }
            QCheckBox {
                spacing: 6px;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }
            """
        )

        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.start_button = QPushButton("▶ Start")
        self.start_button.clicked.connect(self.start_clicking)
        toolbar.addWidget(self.start_button)

        self.stop_button = QPushButton("■ Stop")
        self.stop_button.clicked.connect(self.stop_clicking)
        toolbar.addWidget(self.stop_button)

        self.hotkeys_button = QPushButton("Hotkeys")
        self.hotkeys_button.clicked.connect(self.open_hotkey_dialog)
        toolbar.addWidget(self.hotkeys_button)

        root = QWidget()
        container = QVBoxLayout(root)
        container.setContentsMargins(12, 8, 12, 8)
        container.setSpacing(8)

        container.addWidget(self._build_click_config_group())
        container.addWidget(self._build_loop_timer_group())
        container.addWidget(self._build_start_delay_group())
        container.addWidget(self._build_recording_group())
        container.addStretch(1)

        self.setCentralWidget(root)
        self._build_status_panel()

    def _build_click_config_group(self) -> QGroupBox:
        group = QGroupBox("Click Configuration")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setSpacing(8)

        self.button_combo = QComboBox()
        self.button_combo.addItems(["Left", "Right", "Middle"])
        form.addRow("Button", self.button_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Single", "Double", "Triple"])
        form.addRow("Type", self.type_combo)

        interval_row = QHBoxLayout()
        self.interval_h_spin = QSpinBox()
        self.interval_h_spin.setRange(0, 23)
        self.interval_h_spin.setFixedWidth(60)
        interval_row.addWidget(QLabel("h"))
        interval_row.addWidget(self.interval_h_spin)

        self.interval_m_spin = QSpinBox()
        self.interval_m_spin.setRange(0, 59)
        self.interval_m_spin.setFixedWidth(60)
        interval_row.addWidget(QLabel("m"))
        interval_row.addWidget(self.interval_m_spin)

        self.interval_s_spin = QSpinBox()
        self.interval_s_spin.setRange(0, 59)
        self.interval_s_spin.setFixedWidth(60)
        interval_row.addWidget(QLabel("s"))
        interval_row.addWidget(self.interval_s_spin)

        self.interval_ms_spin = QSpinBox()
        self.interval_ms_spin.setRange(0, 999)
        self.interval_ms_spin.setFixedWidth(70)
        interval_row.addWidget(QLabel("ms"))
        interval_row.addWidget(self.interval_ms_spin)

        interval_row.addStretch(1)
        self.total_label = QLabel("= 100ms")
        self.total_label.setStyleSheet("color: #6B7280; font-weight: 600;")
        interval_row.addWidget(self.total_label)

        interval_widget = QWidget()
        interval_widget.setLayout(interval_row)
        form.addRow("Interval", interval_widget)

        self.location_combo = QComboBox()
        self.location_combo.addItems(["Follow cursor", "Fixed XY"])
        self.location_combo.currentTextChanged.connect(self._update_location_controls)
        form.addRow("Location", self.location_combo)

        self.random_offset_check = QCheckBox("Random Offset")
        self.random_offset_spin = QSpinBox()
        self.random_offset_spin.setRange(1, 50)
        self.random_offset_spin.setValue(5)
        self.random_offset_spin.setFixedWidth(70)
        random_row = QHBoxLayout()
        random_row.addWidget(self.random_offset_check)
        random_row.addWidget(QLabel("±px"))
        random_row.addWidget(self.random_offset_spin)
        random_row.addStretch(1)
        random_widget = QWidget()
        random_widget.setLayout(random_row)
        form.addRow("Location", random_widget)

        fixed_grid = QGridLayout()
        fixed_grid.setHorizontalSpacing(6)
        self.x_spin = QSpinBox()
        self.y_spin = QSpinBox()
        for spin in (self.x_spin, self.y_spin):
            spin.setRange(0, 99999)
        self.pick_button = QPushButton("Pick on screen")
        self.pick_button.clicked.connect(self.pick_fixed_position)
        fixed_grid.addWidget(QLabel("X"), 0, 0)
        fixed_grid.addWidget(self.x_spin, 0, 1)
        fixed_grid.addWidget(QLabel("Y"), 0, 2)
        fixed_grid.addWidget(self.y_spin, 0, 3)
        fixed_grid.addWidget(self.pick_button, 1, 0, 1, 4)
        fixed_widget = QWidget()
        fixed_widget.setLayout(fixed_grid)
        form.addRow("Fixed XY", fixed_widget)
        self.fixed_widget = fixed_widget

        def update_total():
            total = (self.interval_h_spin.value() * 3600000 +
                    self.interval_m_spin.value() * 60000 +
                    self.interval_s_spin.value() * 1000 +
                    self.interval_ms_spin.value())
            if total == 0:
                total = 10
            self.total_label.setText(f"= {total}ms")

        self.interval_h_spin.valueChanged.connect(update_total)
        self.interval_m_spin.valueChanged.connect(update_total)
        self.interval_s_spin.valueChanged.connect(update_total)
        self.interval_ms_spin.valueChanged.connect(update_total)

        return group

    def _build_loop_timer_group(self) -> QGroupBox:
        group = QGroupBox("Loop & Timer")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        repeat_box = QGroupBox("Repeat")
        repeat_layout = QVBoxLayout(repeat_box)
        self.repeat_infinite_radio = QRadioButton("Infinite")
        self.repeat_fixed_radio = QRadioButton("Fixed count")
        self.repeat_count_spin = QSpinBox()
        self.repeat_count_spin.setRange(1, 999999)
        self.repeat_group = QButtonGroup(self)
        self.repeat_group.addButton(self.repeat_infinite_radio)
        self.repeat_group.addButton(self.repeat_fixed_radio)
        self.repeat_infinite_radio.toggled.connect(self._update_repeat_controls)
        repeat_layout.addWidget(self.repeat_infinite_radio)
        repeat_row = QHBoxLayout()
        repeat_row.addWidget(self.repeat_fixed_radio)
        repeat_row.addWidget(self.repeat_count_spin)
        repeat_layout.addLayout(repeat_row)

        timer_box = QGroupBox("Timer")
        timer_layout = QVBoxLayout(timer_box)
        self.timer_none_radio = QRadioButton("None")
        self.timer_stop_radio = QRadioButton("Stop after N seconds")
        self.timer_seconds_spin = QSpinBox()
        self.timer_seconds_spin.setRange(1, 999999)
        self.timer_group = QButtonGroup(self)
        self.timer_group.addButton(self.timer_none_radio)
        self.timer_group.addButton(self.timer_stop_radio)
        self.timer_none_radio.toggled.connect(self._update_timer_controls)
        timer_layout.addWidget(self.timer_none_radio)
        timer_row = QHBoxLayout()
        timer_row.addWidget(self.timer_stop_radio)
        timer_row.addWidget(self.timer_seconds_spin)
        timer_layout.addLayout(timer_row)

        grid.addWidget(repeat_box, 0, 0)
        grid.addWidget(timer_box, 0, 1)
        return group

    def _build_start_delay_group(self) -> QGroupBox:
        group = QGroupBox("Delay Before Start")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.start_delay_spin = QSpinBox()
        self.start_delay_spin.setRange(0, 60)
        form.addRow("Seconds", self.start_delay_spin)
        return group

    def _build_recording_group(self) -> QGroupBox:
        group = QGroupBox("Record & Playback")
        layout = QVBoxLayout(group)

        # Record controls
        record_row = QHBoxLayout()
        self.record_button = QPushButton("Record")
        self.record_button.setObjectName("recordButton")
        self.record_button.clicked.connect(self._toggle_recording)
        record_row.addWidget(self.record_button)

        self.record_status = QLabel("Ready")
        record_row.addWidget(self.record_status)
        record_row.addStretch(1)

        self.play_button = QPushButton("Play Recording ▶")
        self.play_button.setObjectName("playButton")
        self.play_button.clicked.connect(self._start_playback)
        record_row.addWidget(self.play_button)

        self.clear_rec_button = QPushButton("Clear")
        self.clear_rec_button.setObjectName("clearButton")
        self.clear_rec_button.clicked.connect(self._clear_recording)
        record_row.addWidget(self.clear_rec_button)

        layout.addLayout(record_row)

        # Recording list
        self.record_list = QListWidget()
        self.record_list.setMaximumHeight(120)
        layout.addWidget(QLabel("Captured Clicks:"))
        layout.addWidget(self.record_list)

        return group

    def _build_status_panel(self) -> None:
        status = QStatusBar(self)
        status.setFixedHeight(68)
        panel = QWidget()
        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(8, 4, 8, 4)
        panel_layout.setSpacing(18)

        self.state_label = QLabel("State: Idle")
        self.clicks_label = QLabel("Clicks this session: 0")
        self.last_time_label = QLabel("Last click time: --:--:--")

        panel_layout.addWidget(self.state_label)
        panel_layout.addWidget(self.clicks_label)
        panel_layout.addWidget(self.last_time_label)
        panel_layout.addStretch(1)
        status.addPermanentWidget(panel, 1)
        self.setStatusBar(status)

    def _update_location_controls(self) -> None:
        fixed = self.location_combo.currentText() == "Fixed XY"
        self.fixed_widget.setVisible(fixed)

    def _update_repeat_controls(self) -> None:
        self.repeat_count_spin.setEnabled(self.repeat_fixed_radio.isChecked())

    def _update_timer_controls(self) -> None:
        self.timer_seconds_spin.setEnabled(self.timer_stop_radio.isChecked())

    def _update_status(self, state: str) -> None:
        self.state_label.setText(f"State: {state}")

    def _update_hotkey_tooltips(self) -> None:
        start_hotkey = self.config.get("hotkey_start", "F6")
        stop_hotkey = self.config.get("hotkey_stop", "F7")
        self.start_button.setText(f"▶ Start ({start_hotkey})")
        self.stop_button.setText(f"■ Stop ({stop_hotkey})")
        self.start_button.setToolTip(f"Start/Stop ({start_hotkey})")
        self.stop_button.setToolTip(f"Emergency Stop ({stop_hotkey})")

    def _update_recording_ui(self) -> None:
        has_recording = len(self.recording) > 0
        self.play_button.setEnabled(has_recording)
        self.clear_rec_button.setEnabled(has_recording)
        self._refresh_record_list()

    def _refresh_record_list(self) -> None:
        self.record_list.clear()
        for i, click in enumerate(self.recording):
            delay = click.get("delay_ms", 0)
            item = QListWidgetItem(
                f"{i+1}. Click at ({click['x']}, {click['y']}) - delay: {delay}ms"
            )
            self.record_list.addItem(item)

    def _get_interval_ms(self) -> int:
        total = (self.interval_h_spin.value() * 3600000 +
                self.interval_m_spin.value() * 60000 +
                self.interval_s_spin.value() * 1000 +
                self.interval_ms_spin.value())
        return max(10, total)

    def _toggle_recording(self) -> None:
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.recorded_clicks = []
        self.record_start_time = time.time() * 1000
        self.record_button.setText("Stop Recording")
        self.record_button.setStyleSheet(self.record_button.styleSheet() + " background-color: #DC2626;")
        self.record_status.setText("Recording... 0 clicks captured")
        self.statusBar().showMessage("Recording active - click anywhere to capture positions")

        def on_click(x: int, y: int, _button: mouse.Button, pressed: bool) -> bool:
            if pressed and _button == mouse.Button.left:
                current_time = time.time() * 1000
                if len(self.recorded_clicks) == 0:
                    delay_ms = 0
                else:
                    delay_ms = int(current_time - self.recorded_clicks[-1]["timestamp"])
                self.recorded_clicks.append({
                    "x": int(x),
                    "y": int(y),
                    "delay_ms": delay_ms,
                    "timestamp": current_time,
                })
                count = len(self.recorded_clicks)
                self.record_status.setText(f"Recording... {count} clicks captured")
                if count >= 20:
                    self._stop_recording()
                    QMessageBox.warning(self, "Maximum Reached", "Maximum 20 clicks per recording reached!")
            return True

        self.record_mouse_listener = mouse.Listener(on_click=on_click)
        self.record_mouse_listener.start()

    def _stop_recording(self) -> None:
        if not self.is_recording:
            return
        self.is_recording = False
        if self.record_mouse_listener:
            self.record_mouse_listener.stop()
            self.record_mouse_listener = None

        self.recording = [
            {"x": c["x"], "y": c["y"], "delay_ms": c["delay_ms"]}
            for c in self.recorded_clicks
        ]
        self.config["recording"] = self.recording

        self.record_button.setText("Record")
        self.record_button.setStyleSheet("")
        self.record_status.setText(f"Stopped - {len(self.recording)} clicks saved")
        self.statusBar().showMessage("Recording stopped", 3000)
        self._update_recording_ui()

    def _clear_recording(self) -> None:
        self.recording = []
        self.config["recording"] = []
        self.record_status.setText("Ready")
        self._update_recording_ui()

    def _start_playback(self) -> None:
        if len(self.recording) == 0:
            return
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_stop_event.set()
            return

        self.playback_stop_event.clear()
        repeat_count = 1 if self.repeat_group.checkedButton() == self.repeat_infinite_radio else int(self.repeat_count_spin.value())

        def playback_loop():
            for iteration in range(repeat_count if repeat_count > 0 else 999999999):
                if self.playback_stop_event.is_set():
                    break
                for click_data in self.recording:
                    if self.playback_stop_event.is_set():
                        break
                    delay_sec = click_data["delay_ms"] / 1000.0
                    target_x = int(click_data["x"])
                    target_y = int(click_data["y"])

                    if delay_sec > 0:
                        time.sleep(delay_sec)

                    if self.playback_stop_event.is_set():
                        break

                    try:
                        import pyautogui
                        pyautogui.click(x=target_x, y=target_y, clicks=1, button="left")
                    except Exception as e:
                        self._logger.exception("Playback click error: %s", e)

        self.playback_thread = threading.Thread(target=playback_loop, daemon=True)
        self.playback_thread.start()

    def _load_config_to_ui(self) -> None:
        self.button_combo.setCurrentText(self.config.get("button", "Left"))
        behaviour_value = str(
            self.config.get("click_behaviour", self.config.get("type", "Single"))
        ).strip().lower()
        behaviour_label = CLICK_BEHAVIOUR_VALUE_TO_LABEL.get(behaviour_value, "Single")
        self.type_combo.setCurrentText(behaviour_label)

        self.interval_h_spin.setValue(self.config.get("interval_h", 0))
        self.interval_m_spin.setValue(self.config.get("interval_m", 0))
        self.interval_s_spin.setValue(self.config.get("interval_s", 0))
        self.interval_ms_spin.setValue(self.config.get("interval_ms", 100))

        self.location_combo.setCurrentText(self.config.get("location_mode", "Follow cursor"))
        self.x_spin.setValue(int(self.config.get("x", 0)))
        self.y_spin.setValue(int(self.config.get("y", 0)))

        self.random_offset_check.setChecked(self.config.get("random_offset_enabled", False))
        self.random_offset_spin.setValue(self.config.get("random_offset_px", 5))

        if self.config.get("repeat_mode", "Infinite") == "Fixed count":
            self.repeat_fixed_radio.setChecked(True)
        else:
            self.repeat_infinite_radio.setChecked(True)
        self.repeat_count_spin.setValue(int(self.config.get("repeat_count", 10)))

        if self.config.get("timer_mode", "None") == "Stop after N seconds":
            self.timer_stop_radio.setChecked(True)
        else:
            self.timer_none_radio.setChecked(True)
        self.timer_seconds_spin.setValue(int(self.config.get("timer_seconds", 10)))

        self.start_delay_spin.setValue(int(self.config.get("start_delay", 3)))
        self._update_hotkey_tooltips()
        self.recording = self.config.get("recording", [])
        self._update_recording_ui()

    def _collect_config_from_ui(self) -> dict:
        interval_ms = self._get_interval_ms()

        data = {
            "button": self.button_combo.currentText(),
            "type": self.type_combo.currentText(),
            "click_behaviour": CLICK_BEHAVIOUR_LABEL_TO_VALUE.get(
                self.type_combo.currentText(), "single"
            ),
            "interval_h": self.interval_h_spin.value(),
            "interval_m": self.interval_m_spin.value(),
            "interval_s": self.interval_s_spin.value(),
            "interval_ms": self.interval_ms_spin.value(),
            "location_mode": self.location_combo.currentText(),
            "x": int(self.x_spin.value()),
            "y": int(self.y_spin.value()),
            "random_offset_enabled": self.random_offset_check.isChecked(),
            "random_offset_px": self.random_offset_spin.value(),
            "repeat_mode": "Fixed count" if self.repeat_fixed_radio.isChecked() else "Infinite",
            "repeat_count": int(self.repeat_count_spin.value()),
            "timer_mode": "Stop after N seconds" if self.timer_stop_radio.isChecked() else "None",
            "timer_seconds": int(self.timer_seconds_spin.value()),
            "start_delay": int(self.start_delay_spin.value()),
            "tray_on_close": self.tray_on_close_action.isChecked() if hasattr(self, 'tray_on_close_action') else self.config.get("tray_on_close", True),
            "hotkey_start": self.config.get("hotkey_start", "F6"),
            "hotkey_stop": self.config.get("hotkey_stop", "F7"),
            "recording": self.recording,
        }
        return data

    def _build_click_config_for_thread(self) -> dict:
        data = self._collect_config_from_ui()
        return data

    def _start_hotkey_listener(self) -> None:
        if self.hotkey_listener is not None and self.hotkey_listener.is_alive():
            return
        self.hotkey_listener = GlobalHotkeyListener(
            self.hotkey_bridge,
            self.config.get("hotkey_start", "F6"),
            self.config.get("hotkey_stop", "F7"),
        )
        self.hotkey_listener.start()
        self._update_hotkey_tooltips()

    def _ensure_hotkey_listener_alive(self) -> None:
        if self.hotkey_listener is not None and self.hotkey_listener.is_alive():
            return
        self._logger.warning("Hotkey listener dead; restarting")
        self._start_hotkey_listener()

    def _thread_running(self) -> bool:
        return self.clicker_thread is not None and self.clicker_thread.isRunning()

    def start_clicking(self) -> None:
        if self._thread_running() or self.countdown_timer.isActive():
            return
        self.remaining_delay = int(self.start_delay_spin.value())
        if self.remaining_delay > 0:
            self._update_status(f"Waiting ({self.remaining_delay}s)")
            self.countdown_timer.start(1000)
            return
        self._begin_thread()

    def _countdown_tick(self) -> None:
        self.remaining_delay -= 1
        if self.remaining_delay <= 0:
            self.countdown_timer.stop()
            self._begin_thread()
            return
        self._update_status(f"Waiting ({self.remaining_delay}s)")

    def _begin_thread(self) -> None:
        config = self._build_click_config_for_thread()
        self.clicker_thread = ClickerThread(config)
        self.clicker_thread.state_changed.connect(self._update_status)
        self.clicker_thread.click_count_changed.connect(self._on_click_count_changed)
        self.clicker_thread.last_click_time_changed.connect(self._on_last_click_time_changed)
        self.clicker_thread.finished_with_reason.connect(self._on_clicker_finished)
        self.clicker_thread.start()

    def stop_clicking(self) -> None:
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self._update_status("Stopped")
        if self._thread_running():
            self.clicker_thread.stop()
            self.clicker_thread.wait(1500)
        else:
            self._update_status("Stopped")

    @pyqtSlot()
    def toggle_start_stop(self) -> None:
        if self._thread_running() or self.countdown_timer.isActive():
            self.stop_clicking()
        else:
            self.start_clicking()

    @pyqtSlot()
    def emergency_stop(self) -> None:
        self.stop_clicking()

    @pyqtSlot(int)
    def _on_click_count_changed(self, count: int) -> None:
        self.session_clicks = count
        self.clicks_label.setText(f"Clicks this session: {count}")

    @pyqtSlot(str)
    def _on_last_click_time_changed(self, value: str) -> None:
        self.last_time_label.setText(f"Last click time: {value}")

    @pyqtSlot(str)
    def _on_clicker_finished(self, reason: str) -> None:
        self._update_status(reason)

    def open_hotkey_dialog(self) -> None:
        dialog = HotkeyDialog(
            self.config.get("hotkey_start", "F6"),
            self.config.get("hotkey_stop", "F7"),
            self,
        )
        if dialog.exec():
            start, stop = dialog.get_hotkeys()
            self.config["hotkey_start"] = start
            self.config["hotkey_stop"] = stop
            if self.hotkey_listener is not None:
                self.hotkey_listener.update_hotkeys(start, stop)
            self._update_hotkey_tooltips()

    def pick_fixed_position(self) -> None:
        self.hide()
        QTimer.singleShot(3000, self._capture_position_click)

    def _capture_position_click(self) -> None:
        captured = {"x": None, "y": None}
        done = threading.Event()

        def on_click(x: int, y: int, _button: mouse.Button, pressed: bool) -> bool:
            if pressed:
                captured["x"] = int(x)
                captured["y"] = int(y)
                done.set()
                return False
            return True

        listener = mouse.Listener(on_click=on_click)
        listener.start()

        def await_pick() -> None:
            done.wait(timeout=15)
            listener.stop()
            QMetaObject.invokeMethod(
                self,
                "_apply_picked_position",
                Qt.ConnectionType.QueuedConnection,
            )

        self._pending_pick = captured
        threading.Thread(target=await_pick, daemon=True).start()

    @pyqtSlot()
    def _apply_picked_position(self) -> None:
        data = getattr(self, "_pending_pick", {"x": None, "y": None})
        if data["x"] is not None and data["y"] is not None:
            self.x_spin.setValue(int(data["x"]))
            self.y_spin.setValue(int(data["y"]))
            self.location_combo.setCurrentText("Fixed XY")
        else:
            QMessageBox.information(self, "Pick Position", "No click captured. Try again.")
        self.showNormal()
        self.activateWindow()

    def _setup_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "icon.ico"
        )
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        # If no icon, just use default system tray icon (no need to set)
        self.tray_icon.setToolTip("AutoClicker")

        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        start_action = QAction("Start", self)
        start_action.triggered.connect(self.start_clicking)
        tray_menu.addAction(start_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _quit_application(self) -> None:
        self.stop_clicking()
        self.hotkey_watchdog.stop()
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        self._save_config_on_close()
        QApplication.quit()

    def _save_config_on_close(self) -> None:
        merged = self._collect_config_from_ui()
        merged["hotkey_start"] = self.config.get("hotkey_start", "F6")
        merged["hotkey_stop"] = self.config.get("hotkey_stop", "F7")
        self.settings_store.save(merged)

    def closeEvent(self, event) -> None:
        tray_on_close = self.config.get("tray_on_close", True)
        if tray_on_close and hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "AutoClicker",
                "AutoClicker is still running. Right-click to access controls.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._save_config_on_close()
            event.ignore()
        else:
            self.stop_clicking()
            self.hotkey_watchdog.stop()
            if self.hotkey_listener is not None:
                self.hotkey_listener.stop()
            self._save_config_on_close()
            event.accept()
