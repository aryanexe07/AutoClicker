import threading
from typing import Optional

from pynput import keyboard, mouse
from PyQt6.QtCore import QMetaObject, QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.clicker import ClickerThread
from core.settings import SettingsStore
from ui.hotkey_dialog import HotkeyDialog


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
        self.start_hotkey = start_hotkey
        self.stop_hotkey = stop_hotkey
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    @staticmethod
    def _to_pynput_expression(hotkey: str) -> str:
        cleaned = hotkey.lower().replace(" ", "")
        parts = [part for part in cleaned.split("+") if part]
        mapped = []
        for part in parts:
            if part in {"ctrl", "control"}:
                mapped.append("<ctrl>")
            elif part in {"alt"}:
                mapped.append("<alt>")
            elif part in {"shift"}:
                mapped.append("<shift>")
            elif part in {"cmd", "win", "super", "windows"}:
                mapped.append("<cmd>")
            else:
                mapped.append(part)
        return "+".join(mapped)

    def run(self) -> None:
        mapping = {
            self._to_pynput_expression(self.start_hotkey): self._on_toggle,
            self._to_pynput_expression(self.stop_hotkey): self._on_stop,
        }
        try:
            with keyboard.GlobalHotKeys(mapping) as listener:
                self._listener = listener
                listener.join()
        except Exception as exc:
            print(f"[AutoClicker] hotkey listener error: {exc}")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _on_toggle(self) -> None:
        QMetaObject.invokeMethod(self.bridge, "emit_toggle", Qt.ConnectionType.QueuedConnection)

    def _on_stop(self) -> None:
        QMetaObject.invokeMethod(self.bridge, "emit_stop", Qt.ConnectionType.QueuedConnection)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Clicker")
        self.setFixedSize(420, 520)

        self.settings_store = SettingsStore()
        self.config = self.settings_store.load()

        self.clicker_thread: Optional[ClickerThread] = None
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.remaining_delay = 0
        self.session_clicks = 0
        self.hotkey_listener: Optional[GlobalHotkeyListener] = None

        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.toggle_requested.connect(self.toggle_start_stop)
        self.hotkey_bridge.stop_requested.connect(self.emergency_stop)

        self._build_ui()
        self._load_config_to_ui()
        self._update_location_controls()
        self._update_repeat_controls()
        self._update_timer_controls()
        self._update_status("Idle")
        self._restart_hotkey_listener()

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
            QComboBox, QSpinBox, QPushButton {
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
        self.type_combo.addItems(["Single", "Double"])
        form.addRow("Type", self.type_combo)

        interval_row = QHBoxLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 999999)
        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["ms", "s"])
        interval_row.addWidget(self.interval_spin)
        interval_row.addWidget(self.interval_unit_combo)
        interval_widget = QWidget()
        interval_widget.setLayout(interval_row)
        form.addRow("Interval", interval_widget)

        self.location_combo = QComboBox()
        self.location_combo.addItems(["Follow cursor", "Fixed XY"])
        self.location_combo.currentTextChanged.connect(self._update_location_controls)
        form.addRow("Location", self.location_combo)

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
        start_hotkey = self.config["hotkey_start"]
        stop_hotkey = self.config["hotkey_stop"]
        self.start_button.setText(f"▶ Start ({start_hotkey})")
        self.stop_button.setText(f"■ Stop ({stop_hotkey})")
        self.start_button.setToolTip(f"Start/Stop ({start_hotkey})")
        self.stop_button.setToolTip(f"Emergency Stop ({stop_hotkey})")

    def _load_config_to_ui(self) -> None:
        self.button_combo.setCurrentText(self.config["button"])
        self.type_combo.setCurrentText(self.config["type"])

        interval_ms = int(self.config["interval_ms"])
        if interval_ms >= 1000 and interval_ms % 1000 == 0:
            self.interval_spin.setValue(interval_ms // 1000)
            self.interval_unit_combo.setCurrentText("s")
        else:
            self.interval_spin.setValue(interval_ms)
            self.interval_unit_combo.setCurrentText("ms")

        self.location_combo.setCurrentText(self.config["location_mode"])
        self.x_spin.setValue(int(self.config["x"]))
        self.y_spin.setValue(int(self.config["y"]))

        if self.config["repeat_mode"] == "Fixed count":
            self.repeat_fixed_radio.setChecked(True)
        else:
            self.repeat_infinite_radio.setChecked(True)
        self.repeat_count_spin.setValue(int(self.config["repeat_count"]))

        if self.config["timer_mode"] == "Stop after N seconds":
            self.timer_stop_radio.setChecked(True)
        else:
            self.timer_none_radio.setChecked(True)
        self.timer_seconds_spin.setValue(int(self.config["timer_seconds"]))

        self.start_delay_spin.setValue(int(self.config["start_delay"]))
        self._update_hotkey_tooltips()

    def _collect_config_from_ui(self) -> dict:
        interval_value = int(self.interval_spin.value())
        interval_ms = interval_value if self.interval_unit_combo.currentText() == "ms" else interval_value * 1000

        return {
            "button": self.button_combo.currentText(),
            "type": self.type_combo.currentText(),
            "interval_ms": interval_ms,
            "location_mode": self.location_combo.currentText(),
            "x": int(self.x_spin.value()),
            "y": int(self.y_spin.value()),
            "repeat_mode": "Fixed count" if self.repeat_fixed_radio.isChecked() else "Infinite",
            "repeat_count": int(self.repeat_count_spin.value()),
            "timer_mode": "Stop after N seconds" if self.timer_stop_radio.isChecked() else "None",
            "timer_seconds": int(self.timer_seconds_spin.value()),
            "start_delay": int(self.start_delay_spin.value()),
            "hotkey_start": self.config.get("hotkey_start", "F6"),
            "hotkey_stop": self.config.get("hotkey_stop", "F7"),
        }

    def _build_click_config_for_thread(self) -> dict:
        data = self._collect_config_from_ui()
        data["interval_seconds"] = float(data["interval_ms"]) / 1000.0
        return data

    def _restart_hotkey_listener(self) -> None:
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        self.hotkey_listener = GlobalHotkeyListener(
            self.hotkey_bridge,
            self.config.get("hotkey_start", "F6"),
            self.config.get("hotkey_stop", "F7"),
        )
        self.hotkey_listener.start()
        self._update_hotkey_tooltips()

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
            self._restart_hotkey_listener()

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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.stop_clicking()
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        merged = self._collect_config_from_ui()
        merged["hotkey_start"] = self.config.get("hotkey_start", "F6")
        merged["hotkey_stop"] = self.config.get("hotkey_stop", "F7")
        self.settings_store.save(merged)
        super().closeEvent(event)
