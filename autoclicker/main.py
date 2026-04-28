import sys
import json
import random
import logging
import threading
import time
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QRadioButton,
    QButtonGroup, QCheckBox, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QSizePolicy, QMessageBox, QFileDialog,
    QSystemTrayIcon, QMenu, QProgressBar, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QKeySequence, QCursor

import pyautogui
from pynput import mouse as pmouse, keyboard as pkeyboard

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_PATH = Path(__file__).parent / "autoclicker.log"
logging.basicConfig(filename=str(LOG_PATH), level=logging.ERROR,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "autoclicker_config.json"

DEFAULTS = {
    "interval_h": 0, "interval_m": 0, "interval_s": 0, "interval_ms": 100,
    "click_type": "Left", "click_behaviour": "Single",
    "location_mode": "Current", "fixed_x": 0, "fixed_y": 0,
    "loop_mode": "Infinite", "fixed_count": 10,
    "timer_enabled": False, "timer_seconds": 10,
    "delay_before_start": 3,
    "random_offset_enabled": False, "random_offset_px": 5,
    "multipoint_sequence": [],
    "last_preset": "Custom",
    "hotkey_start": "f6", "hotkey_stop": "f7",
}


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in cfg:
                    cfg[k] = v
        except Exception as e:
            logging.error(f"Config load error: {e}")
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logging.error(f"Config save error: {e}")


# ── Stylesheet ─────────────────────────────────────────────────────────────────
STYLE = """
QWidget {
    background-color: #0e0e0e;
    color: #e0e0e0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}

QMainWindow {
    background-color: #0e0e0e;
}

/* Group boxes */
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    color: #555;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #444;
}

/* Buttons */
QPushButton {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    padding: 7px 14px;
    font-family: "Consolas", monospace;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #242424;
    border-color: #444;
}
QPushButton:pressed {
    background-color: #111;
}
QPushButton#btn_start {
    background-color: #1a1a1a;
    color: #00e676;
    border: 1px solid #00e676;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 20px;
    letter-spacing: 1px;
}
QPushButton#btn_start:hover {
    background-color: #00e676;
    color: #0e0e0e;
}
QPushButton#btn_stop {
    background-color: #1a1a1a;
    color: #ff3d3d;
    border: 1px solid #ff3d3d;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 20px;
    letter-spacing: 1px;
}
QPushButton#btn_stop:hover {
    background-color: #ff3d3d;
    color: #0e0e0e;
}
QPushButton#btn_record {
    color: #ff3d3d;
    border-color: #ff3d3d;
}
QPushButton#btn_record:hover {
    background-color: #ff3d3d;
    color: #0e0e0e;
}
QPushButton#btn_play {
    color: #00e676;
    border-color: #00e676;
}
QPushButton#btn_play:hover {
    background-color: #00e676;
    color: #0e0e0e;
}
QPushButton#btn_pick {
    color: #64b5f6;
    border-color: #64b5f6;
    padding: 5px 10px;
    font-size: 11px;
}
QPushButton#btn_pick:hover {
    background-color: #64b5f6;
    color: #0e0e0e;
}

/* Inputs */
QSpinBox, QComboBox {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 4px 6px;
    color: #e0e0e0;
    selection-background-color: #333;
}
QSpinBox:focus, QComboBox:focus {
    border-color: #444;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    width: 8px;
    height: 8px;
}
QComboBox QAbstractItemView {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    selection-background-color: #222;
    color: #e0e0e0;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1e1e1e;
    border: none;
    width: 14px;
}

/* Radio / Check */
QRadioButton, QCheckBox {
    color: #aaa;
    spacing: 6px;
}
QRadioButton:checked, QCheckBox:checked {
    color: #e0e0e0;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #333;
    border-radius: 7px;
    background-color: #141414;
}
QCheckBox::indicator {
    border-radius: 3px;
}
QRadioButton::indicator:checked {
    background-color: #00e676;
    border-color: #00e676;
}
QCheckBox::indicator:checked {
    background-color: #00e676;
    border-color: #00e676;
}

/* Labels */
QLabel#lbl_warning {
    color: #ff9800;
    font-size: 11px;
}
QLabel#lbl_advisory {
    color: #fdd835;
    font-size: 11px;
}
QLabel#lbl_status {
    color: #555;
    font-size: 11px;
    letter-spacing: 1px;
}
QLabel#lbl_stat_val {
    color: #00e676;
    font-size: 13px;
    font-weight: bold;
}

/* Progress */
QProgressBar {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #00e676;
    border-radius: 3px;
}

/* Table */
QTableWidget {
    background-color: #0e0e0e;
    gridline-color: #1e1e1e;
    border: 1px solid #1e1e1e;
    border-radius: 4px;
    color: #ccc;
}
QTableWidget::item:selected {
    background-color: #1e1e1e;
    color: #fff;
}
QHeaderView::section {
    background-color: #141414;
    color: #555;
    border: none;
    border-bottom: 1px solid #2a2a2a;
    padding: 4px;
    font-size: 10px;
    letter-spacing: 1px;
}

/* Scrollbar */
QScrollBar:vertical {
    background: #0e0e0e;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #2a2a2a;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QFrame#divider {
    background-color: #1e1e1e;
    max-height: 1px;
}
"""

# ── Click Worker ───────────────────────────────────────────────────────────────
class ClickWorker(QObject):
    finished = pyqtSignal()
    tick = pyqtSignal()

    def __init__(self, cfg, multipoint=None):
        super().__init__()
        self.cfg = cfg
        self.multipoint = multipoint
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        cfg = self.cfg

        interval_ms = (cfg["interval_h"] * 3600 + cfg["interval_m"] * 60 +
                       cfg["interval_s"]) * 1000 + cfg["interval_ms"]
        interval_ms = max(10, interval_ms)

        btn = cfg["click_type"].lower()
        behaviour = cfg["click_behaviour"]
        loop_mode = cfg["loop_mode"]
        fixed_count = cfg["fixed_count"]
        timer_enabled = cfg["timer_enabled"]
        timer_seconds = cfg["timer_seconds"]
        offset_enabled = cfg["random_offset_enabled"]
        offset_px = cfg["random_offset_px"]
        location_mode = cfg["location_mode"]
        fixed_x = cfg["fixed_x"]
        fixed_y = cfg["fixed_y"]

        multipoint = self.multipoint  # reuse field for multipoint too
        use_multipoint = isinstance(multipoint, list) and len(multipoint) > 0

        start_time = time.time()
        click_count = 0

        pyautogui.FAILSAFE = False

        def do_click(x, y):
            if offset_enabled:
                x += random.randint(-offset_px, offset_px)
                y += random.randint(-offset_px, offset_px)
            if behaviour == "Single":
                pyautogui.click(x, y, button=btn)
            elif behaviour == "Double":
                pyautogui.doubleClick(x, y, button=btn)
            elif behaviour == "Triple":
                pyautogui.click(x, y, button=btn)
                time.sleep(0.03)
                pyautogui.click(x, y, button=btn)
                time.sleep(0.03)
                pyautogui.click(x, y, button=btn)

        while self._running:
            if timer_enabled and (time.time() - start_time) >= timer_seconds:
                break
            if loop_mode == "Fixed" and click_count >= fixed_count:
                break

            if use_multipoint:
                for pt in multipoint:
                    if not self._running:
                        break
                    do_click(pt["x"], pt["y"])
                    self.tick.emit()
                    time.sleep(pt.get("delay_ms", 100) / 1000)
                click_count += 1
            else:
                if location_mode == "Current":
                    pos = pyautogui.position()
                    x, y = pos.x, pos.y
                else:
                    x, y = fixed_x, fixed_y
                try:
                    do_click(x, y)
                except Exception as e:
                    logging.error(f"Click error: {e}")
                self.tick.emit()
                click_count += 1
                time.sleep(interval_ms / 1000)

        self.finished.emit()


# ── Hotkey Listener ────────────────────────────────────────────────────────────
class HotkeyListener(QObject):
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.start_key = "f6"
        self.stop_key = "f7"
        self._listener = None
        self._thread = None

    def update_keys(self, start_key, stop_key):
        self.start_key = start_key.lower()
        self.stop_key = stop_key.lower()

    def _on_press(self, key):
        try:
            k = key.name.lower() if hasattr(key, 'name') else str(key).replace("'", "").lower()
            if k == self.start_key:
                self.start_signal.emit()
            elif k == self.stop_key:
                self.stop_signal.emit()
        except Exception:
            pass

    def start(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        self._listener = pkeyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

    def is_alive(self):
        return self._listener is not None and self._listener.is_alive()





# ── Main Window ────────────────────────────────────────────────────────────────
class AutoClickerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.worker = None
        self.worker_thread = None
        self.is_clicking = False
        self.session_clicks = 0
        self.session_start = None
        self.recent_times = []
        self._warned_fast = False
        self._pick_target = None  # "main" or int (multipoint row)

        self.hotkey = HotkeyListener()
        self.hotkey.start_signal.connect(self.start_clicking)
        self.hotkey.stop_signal.connect(self.stop_clicking)
        self.hotkey.update_keys(self.cfg["hotkey_start"], self.cfg["hotkey_stop"])
        self.hotkey.start()

        self._build_ui()
        self._apply_config()
        self._setup_tray()

        # Hotkey watchdog
        self.watchdog = QTimer()
        self.watchdog.timeout.connect(self._check_hotkey)
        self.watchdog.start(5000)

        # Stats updater
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(250)

        self.setWindowTitle("AutoClicker")
        self.setMinimumWidth(420)
        self.resize(420, 780)
        self.setStyleSheet(STYLE)

    # ── UI BUILD ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Top bar ────────────────────────────────────────────────────────────
        top = QHBoxLayout()
        self.btn_start = QPushButton("▶  START  (F6)")
        self.btn_start.setObjectName("btn_start")
        self.btn_stop = QPushButton("■  STOP  (F7)")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_start.clicked.connect(self.start_clicking)
        self.btn_stop.clicked.connect(self.stop_clicking)
        top.addWidget(self.btn_start)
        top.addWidget(self.btn_stop)
        layout.addLayout(top)

        self.lbl_status = QLabel("IDLE")
        self.lbl_status.setObjectName("lbl_status")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        layout.addWidget(self._divider())

        # Scroll area for everything below
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.inner_layout = QVBoxLayout(inner)
        self.inner_layout.setSpacing(8)
        self.inner_layout.setContentsMargins(0, 0, 4, 0)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        il = self.inner_layout

        # ── Presets ────────────────────────────────────────────────────────────
        g_preset = QGroupBox("Preset")
        gl = QHBoxLayout(g_preset)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(["Custom", "Gaming (Fast)", "Form Filling", "Web Monitor"])
        self.cmb_preset.currentTextChanged.connect(self._apply_preset)
        gl.addWidget(self.cmb_preset)
        il.addWidget(g_preset)

        # ── Click Config ───────────────────────────────────────────────────────
        g_click = QGroupBox("Click Configuration")
        gcl = QGridLayout(g_click)
        gcl.setSpacing(8)

        gcl.addWidget(QLabel("Button"), 0, 0)
        self.cmb_button = QComboBox()
        self.cmb_button.addItems(["Left", "Right", "Middle"])
        gcl.addWidget(self.cmb_button, 0, 1)

        gcl.addWidget(QLabel("Mode"), 1, 0)
        mode_row = QHBoxLayout()
        self.rb_single = QRadioButton("Single")
        self.rb_double = QRadioButton("Double")
        self.rb_triple = QRadioButton("Triple")
        self.rb_single.setChecked(True)
        bg = QButtonGroup(self)
        for rb in (self.rb_single, self.rb_double, self.rb_triple):
            bg.addButton(rb)
            mode_row.addWidget(rb)
        mode_row.addStretch()
        gcl.addLayout(mode_row, 1, 1)

        gcl.addWidget(QLabel("Interval"), 2, 0)
        interval_row = QHBoxLayout()
        self.sp_h = QSpinBox(); self.sp_h.setRange(0, 23); self.sp_h.setSuffix("h"); self.sp_h.setFixedWidth(58)
        self.sp_m = QSpinBox(); self.sp_m.setRange(0, 59); self.sp_m.setSuffix("m"); self.sp_m.setFixedWidth(58)
        self.sp_s = QSpinBox(); self.sp_s.setRange(0, 59); self.sp_s.setSuffix("s"); self.sp_s.setFixedWidth(58)
        self.sp_ms = QSpinBox(); self.sp_ms.setRange(0, 999); self.sp_ms.setSuffix("ms"); self.sp_ms.setFixedWidth(68)
        for sp in (self.sp_h, self.sp_m, self.sp_s, self.sp_ms):
            interval_row.addWidget(sp)
            sp.valueChanged.connect(self._on_interval_changed)
        interval_row.addStretch()
        gcl.addLayout(interval_row, 2, 1)

        self.lbl_interval_total = QLabel("= 100ms")
        self.lbl_interval_total.setStyleSheet("color:#555; font-size:11px;")
        gcl.addWidget(self.lbl_interval_total, 3, 1)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setObjectName("lbl_warning")
        self.lbl_warning.setVisible(False)
        gcl.addWidget(self.lbl_warning, 4, 0, 1, 2)

        il.addWidget(g_click)

        # ── Location ───────────────────────────────────────────────────────────
        g_loc = QGroupBox("Location")
        locl = QVBoxLayout(g_loc)

        loc_radio_row = QHBoxLayout()
        self.rb_current = QRadioButton("Current cursor")
        self.rb_fixed = QRadioButton("Fixed position")
        self.rb_current.setChecked(True)
        bg2 = QButtonGroup(self)
        bg2.addButton(self.rb_current)
        bg2.addButton(self.rb_fixed)
        loc_radio_row.addWidget(self.rb_current)
        loc_radio_row.addWidget(self.rb_fixed)
        loc_radio_row.addStretch()
        locl.addLayout(loc_radio_row)

        fixed_row = QHBoxLayout()
        fixed_row.addWidget(QLabel("X"))
        self.sp_fx = QSpinBox(); self.sp_fx.setRange(0, 9999); self.sp_fx.setFixedWidth(72)
        fixed_row.addWidget(self.sp_fx)
        fixed_row.addWidget(QLabel("Y"))
        self.sp_fy = QSpinBox(); self.sp_fy.setRange(0, 9999); self.sp_fy.setFixedWidth(72)
        fixed_row.addWidget(self.sp_fy)
        self.btn_pick = QPushButton("Pick")
        self.btn_pick.setObjectName("btn_pick")
        self.btn_pick.clicked.connect(lambda: self._start_pick("main"))
        fixed_row.addWidget(self.btn_pick)
        fixed_row.addStretch()
        locl.addLayout(fixed_row)

        offset_row = QHBoxLayout()
        self.chk_offset = QCheckBox("Random offset")
        self.sp_offset = QSpinBox(); self.sp_offset.setRange(1, 50); self.sp_offset.setSuffix(" px"); self.sp_offset.setFixedWidth(72)
        offset_row.addWidget(self.chk_offset)
        offset_row.addWidget(self.sp_offset)
        offset_row.addStretch()
        locl.addLayout(offset_row)

        il.addWidget(g_loc)

        # ── Loop & Timer ───────────────────────────────────────────────────────
        g_loop = QGroupBox("Loop & Timer")
        lpl = QGridLayout(g_loop)
        lpl.setSpacing(8)

        lpl.addWidget(QLabel("Loop"), 0, 0)
        loop_row = QHBoxLayout()
        self.rb_infinite = QRadioButton("Infinite")
        self.rb_fixed_count = QRadioButton("Fixed")
        self.sp_count = QSpinBox(); self.sp_count.setRange(1, 999999); self.sp_count.setFixedWidth(80)
        self.rb_infinite.setChecked(True)
        bg3 = QButtonGroup(self)
        bg3.addButton(self.rb_infinite); bg3.addButton(self.rb_fixed_count)
        loop_row.addWidget(self.rb_infinite)
        loop_row.addWidget(self.rb_fixed_count)
        loop_row.addWidget(self.sp_count)
        loop_row.addStretch()
        lpl.addLayout(loop_row, 0, 1)

        lpl.addWidget(QLabel("Timer"), 1, 0)
        timer_row = QHBoxLayout()
        self.chk_timer = QCheckBox("Stop after")
        self.sp_timer = QSpinBox(); self.sp_timer.setRange(1, 86400); self.sp_timer.setSuffix(" s"); self.sp_timer.setFixedWidth(80)
        timer_row.addWidget(self.chk_timer)
        timer_row.addWidget(self.sp_timer)
        timer_row.addStretch()
        lpl.addLayout(timer_row, 1, 1)

        lpl.addWidget(QLabel("Delay"), 2, 0)
        delay_row = QHBoxLayout()
        self.sp_delay = QSpinBox(); self.sp_delay.setRange(0, 30); self.sp_delay.setSuffix(" s"); self.sp_delay.setFixedWidth(80)
        self.sp_delay.setValue(3)
        delay_row.addWidget(self.sp_delay)
        delay_row.addStretch()
        lpl.addLayout(delay_row, 2, 1)

        il.addWidget(g_loop)

        # ── Multi-Point ────────────────────────────────────────────────────────
        g_multi = QGroupBox("Multi-Point Sequence")
        ml = QVBoxLayout(g_multi)

        mp_mode_row = QHBoxLayout()
        self.rb_normal_mode = QRadioButton("Normal")
        self.rb_multi_mode = QRadioButton("Multi-Point")
        self.rb_normal_mode.setChecked(True)
        bg4 = QButtonGroup(self)
        bg4.addButton(self.rb_normal_mode); bg4.addButton(self.rb_multi_mode)
        mp_mode_row.addWidget(self.rb_normal_mode)
        mp_mode_row.addWidget(self.rb_multi_mode)
        mp_mode_row.addStretch()
        ml.addLayout(mp_mode_row)

        self.mp_table = QTableWidget(0, 5)
        self.mp_table.setHorizontalHeaderLabels(["#", "X", "Y", "Delay(ms)", ""])
        self.mp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mp_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.mp_table.setColumnWidth(4, 60)
        self.mp_table.setFixedHeight(150)
        self.mp_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        ml.addWidget(self.mp_table)

        mp_btn_row = QHBoxLayout()
        self.btn_mp_add = QPushButton("+ Add Point")
        self.btn_mp_add.clicked.connect(self._mp_add_row)
        mp_btn_row.addWidget(self.btn_mp_add)
        mp_btn_row.addStretch()
        ml.addLayout(mp_btn_row)

        il.addWidget(g_multi)



        # ── Stats ──────────────────────────────────────────────────────────────
        g_stats = QGroupBox("Stats")
        sl = QGridLayout(g_stats)
        sl.setSpacing(6)

        def stat_pair(label, row):
            l = QLabel(label)
            l.setStyleSheet("color:#444; font-size:11px;")
            v = QLabel("—")
            v.setObjectName("lbl_stat_val")
            sl.addWidget(l, row, 0)
            sl.addWidget(v, row, 1)
            return v

        self.lbl_total_clicks = stat_pair("Clicks", 0)
        self.lbl_elapsed = stat_pair("Elapsed", 1)
        self.lbl_cps = stat_pair("CPS", 2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        sl.addWidget(self.progress_bar, 3, 0, 1, 2)

        il.addWidget(g_stats)

        # ── Settings ───────────────────────────────────────────────────────────
        g_settings = QGroupBox("Settings")
        stl = QGridLayout(g_settings)
        stl.setSpacing(8)

        stl.addWidget(QLabel("Start hotkey"), 0, 0)
        self.btn_hk_start = QPushButton(self.cfg["hotkey_start"].upper())
        self.btn_hk_start.setCheckable(True)
        self.btn_hk_start.clicked.connect(lambda: self._capture_hotkey("start"))
        stl.addWidget(self.btn_hk_start, 0, 1)

        stl.addWidget(QLabel("Stop hotkey"), 1, 0)
        self.btn_hk_stop = QPushButton(self.cfg["hotkey_stop"].upper())
        self.btn_hk_stop.setCheckable(True)
        self.btn_hk_stop.clicked.connect(lambda: self._capture_hotkey("stop"))
        stl.addWidget(self.btn_hk_stop, 1, 1)



        prof_row = QHBoxLayout()
        self.btn_export = QPushButton("Export Profile")
        self.btn_import = QPushButton("Import Profile")
        self.btn_export.clicked.connect(self._export_profile)
        self.btn_import.clicked.connect(self._import_profile)
        prof_row.addWidget(self.btn_export)
        prof_row.addWidget(self.btn_import)
        stl.addLayout(prof_row, 3, 0, 1, 2)

        il.addWidget(g_settings)
        il.addStretch()

        self._hotkey_capture_target = None

    def _divider(self):
        f = QFrame()
        f.setObjectName("divider")
        f.setFrameShape(QFrame.Shape.HLine)
        return f

    # ── Config Apply ───────────────────────────────────────────────────────────
    def _apply_config(self):
        c = self.cfg
        self.sp_h.setValue(c["interval_h"])
        self.sp_m.setValue(c["interval_m"])
        self.sp_s.setValue(c["interval_s"])
        self.sp_ms.setValue(c["interval_ms"])
        self.cmb_button.setCurrentText(c["click_type"])
        {"Single": self.rb_single, "Double": self.rb_double, "Triple": self.rb_triple}.get(
            c["click_behaviour"], self.rb_single).setChecked(True)
        if c["location_mode"] == "Fixed":
            self.rb_fixed.setChecked(True)
        self.sp_fx.setValue(c["fixed_x"])
        self.sp_fy.setValue(c["fixed_y"])
        self.chk_offset.setChecked(c["random_offset_enabled"])
        self.sp_offset.setValue(c["random_offset_px"])
        if c["loop_mode"] == "Fixed":
            self.rb_fixed_count.setChecked(True)
        self.sp_count.setValue(c["fixed_count"])
        self.chk_timer.setChecked(c["timer_enabled"])
        self.sp_timer.setValue(c["timer_seconds"])
        self.sp_delay.setValue(c["delay_before_start"])

        self.cmb_preset.setCurrentText(c.get("last_preset", "Custom"))
        self._on_interval_changed()
        for pt in c.get("multipoint_sequence", []):
            self._mp_add_row(pt)

    def _read_config(self):
        c = self.cfg
        c["interval_h"] = self.sp_h.value()
        c["interval_m"] = self.sp_m.value()
        c["interval_s"] = self.sp_s.value()
        c["interval_ms"] = self.sp_ms.value()
        c["click_type"] = self.cmb_button.currentText()
        c["click_behaviour"] = ("Triple" if self.rb_triple.isChecked() else
                                "Double" if self.rb_double.isChecked() else "Single")
        c["location_mode"] = "Fixed" if self.rb_fixed.isChecked() else "Current"
        c["fixed_x"] = self.sp_fx.value()
        c["fixed_y"] = self.sp_fy.value()
        c["random_offset_enabled"] = self.chk_offset.isChecked()
        c["random_offset_px"] = self.sp_offset.value()
        c["loop_mode"] = "Fixed" if self.rb_fixed_count.isChecked() else "Infinite"
        c["fixed_count"] = self.sp_count.value()
        c["timer_enabled"] = self.chk_timer.isChecked()
        c["timer_seconds"] = self.sp_timer.value()
        c["delay_before_start"] = self.sp_delay.value()

        c["last_preset"] = self.cmb_preset.currentText()
        c["multipoint_sequence"] = self._read_multipoint()
        return c

    # ── Interval ───────────────────────────────────────────────────────────────
    def _on_interval_changed(self):
        total = (self.sp_h.value() * 3600 + self.sp_m.value() * 60 +
                 self.sp_s.value()) * 1000 + self.sp_ms.value()
        actual = max(10, total)
        self.lbl_interval_total.setText(f"= {actual} ms")

        if total < 10:
            self.lbl_warning.setText("⚠  Minimum interval is 10ms")
            self.lbl_warning.setObjectName("lbl_warning")
            self.lbl_warning.setVisible(True)
        elif total < 50:
            self.lbl_warning.setText("⚠  Very fast — tested stable at 50ms")
            self.lbl_warning.setObjectName("lbl_advisory")
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)

    # ── Presets ────────────────────────────────────────────────────────────────
    def _apply_preset(self, name):
        if name == "Gaming (Fast)":
            self.sp_h.setValue(0); self.sp_m.setValue(0); self.sp_s.setValue(0); self.sp_ms.setValue(50)
            self.rb_infinite.setChecked(True)
            self.rb_current.setChecked(True)
        elif name == "Form Filling":
            self.sp_h.setValue(0); self.sp_m.setValue(0); self.sp_s.setValue(0); self.sp_ms.setValue(500)
            self.rb_fixed_count.setChecked(True); self.sp_count.setValue(1)
            self.rb_fixed.setChecked(True)
        elif name == "Web Monitor":
            self.sp_h.setValue(0); self.sp_m.setValue(0); self.sp_s.setValue(30); self.sp_ms.setValue(0)
            self.rb_infinite.setChecked(True)
            self.rb_fixed.setChecked(True)
            self.chk_offset.setChecked(False)

    # ── Start / Stop ───────────────────────────────────────────────────────────
    def start_clicking(self):
        if self.is_clicking:
            return
        self._read_config()

        total_ms = (self.cfg["interval_h"] * 3600 + self.cfg["interval_m"] * 60 +
                    self.cfg["interval_s"]) * 1000 + self.cfg["interval_ms"]
        if total_ms < 50 and not self._warned_fast:
            r = QMessageBox.question(self, "Fast interval",
                "You're clicking faster than 50ms. Continue?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if r != QMessageBox.StandardButton.Ok:
                return
            self._warned_fast = True

        delay = self.cfg["delay_before_start"]
        if delay > 0:
            self.lbl_status.setText(f"STARTING IN {delay}s…")
            QTimer.singleShot(delay * 1000, self._launch_worker)
        else:
            self._launch_worker()

    def _launch_worker(self):
        self.is_clicking = True
        self.session_clicks = 0
        self.session_start = time.time()
        self.recent_times = []
        self.lbl_status.setText("● CLICKING")
        self.lbl_status.setStyleSheet("color:#00e676; letter-spacing:2px;")

        use_multi = self.rb_multi_mode.isChecked()
        seq = self._read_multipoint() if use_multi else None

        self.worker = ClickWorker(dict(self.cfg), multipoint=seq)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_done)
        self.worker.tick.connect(self._on_tick)
        self.worker_thread.start()

        if self.rb_fixed_count.isChecked():
            self.progress_bar.setMaximum(self.cfg["fixed_count"])
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

    def stop_clicking(self):
        if self.worker:
            self.worker.stop()
        self.is_clicking = False
        self.lbl_status.setText("IDLE")
        self.lbl_status.setStyleSheet("color:#555; letter-spacing:1px;")
        self.progress_bar.setVisible(False)

    def _on_worker_done(self):
        self.stop_clicking()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()

    def _on_tick(self):
        self.session_clicks += 1
        now = time.time()
        self.recent_times.append(now)
        self.recent_times = [t for t in self.recent_times if now - t <= 5]
        if self.rb_fixed_count.isChecked():
            self.progress_bar.setValue(min(self.session_clicks, self.cfg["fixed_count"]))

    # ── Stats ──────────────────────────────────────────────────────────────────
    def _update_stats(self):
        self.lbl_total_clicks.setText(str(self.session_clicks))
        if self.session_start:
            elapsed = int(time.time() - self.session_start)
            self.lbl_elapsed.setText(f"{elapsed//60:02d}:{elapsed%60:02d}")
        cps = len(self.recent_times) / 5.0 if self.recent_times else 0
        self.lbl_cps.setText(f"{cps:.1f}")

    # ── Pick Position ───────────────────────────────────────────────────────────
    def _start_pick(self, target):
        self._pick_target = target
        self.showMinimized()
        self.tray.showMessage("AutoClicker", "Click anywhere to pick position", QSystemTrayIcon.MessageIcon.Information, 3000)
        self._pick_listener = pmouse.Listener(on_click=self._on_pick_click)
        self._pick_listener.start()

    def _on_pick_click(self, x, y, button, pressed):
        if pressed and button == pmouse.Button.left:
            self._pick_listener.stop()
            self.showNormal()
            self.activateWindow()
            if self._pick_target == "main":
                self.sp_fx.setValue(x)
                self.sp_fy.setValue(y)
                self.rb_fixed.setChecked(True)
            elif isinstance(self._pick_target, int):
                row = self._pick_target
                if self.mp_table.item(row, 1):
                    self.mp_table.item(row, 1).setText(str(x))
                    self.mp_table.item(row, 2).setText(str(y))

    # ── Multi-Point ────────────────────────────────────────────────────────────
    def _mp_add_row(self, pt=None):
        if self.mp_table.rowCount() >= 10:
            return
        row = self.mp_table.rowCount()
        self.mp_table.insertRow(row)
        self.mp_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.mp_table.setItem(row, 1, QTableWidgetItem(str(pt["x"] if pt else 0)))
        self.mp_table.setItem(row, 2, QTableWidgetItem(str(pt["y"] if pt else 0)))
        self.mp_table.setItem(row, 3, QTableWidgetItem(str(pt.get("delay_ms", 100) if pt else 100)))
        pick_btn = QPushButton("Pick")
        pick_btn.setObjectName("btn_pick")
        pick_btn.clicked.connect(lambda _, r=row: self._start_pick(r))
        self.mp_table.setCellWidget(row, 4, pick_btn)

    def _read_multipoint(self):
        pts = []
        for r in range(self.mp_table.rowCount()):
            try:
                x = int(self.mp_table.item(r, 1).text())
                y = int(self.mp_table.item(r, 2).text())
                d = int(self.mp_table.item(r, 3).text())
                pts.append({"x": x, "y": y, "delay_ms": d})
            except Exception:
                pass
        return pts















    # ── Hotkeys ────────────────────────────────────────────────────────────────
    def _capture_hotkey(self, target):
        self._hotkey_capture_target = target
        btn = self.btn_hk_start if target == "start" else self.btn_hk_stop
        btn.setText("Press a key…")

    def keyPressEvent(self, event):
        if self._hotkey_capture_target:
            key_name = event.text().lower() or QKeySequence(event.key()).toString().lower()
            if self._hotkey_capture_target == "start":
                self.cfg["hotkey_start"] = key_name
                self.btn_hk_start.setText(key_name.upper())
                self.btn_hk_start.setChecked(False)
            else:
                self.cfg["hotkey_stop"] = key_name
                self.btn_hk_stop.setText(key_name.upper())
                self.btn_hk_stop.setChecked(False)
            self.hotkey.update_keys(self.cfg["hotkey_start"], self.cfg["hotkey_stop"])
            self._hotkey_capture_target = None
        else:
            super().keyPressEvent(event)

    def _check_hotkey(self):
        if not self.hotkey.is_alive():
            logging.error("Hotkey listener died — restarting")
            self.hotkey.start()

    # ── Tray ───────────────────────────────────────────────────────────────────
    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        else:
            self.tray.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        menu.addAction("Show", self.show)
        menu.addAction("Start", self.start_clicking)
        menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def closeEvent(self, event):
        self._quit()

    def _quit(self):
        self.stop_clicking()
        save_config(self._read_config())
        QApplication.quit()

    # ── Profile Export/Import ──────────────────────────────────────────────────
    def _export_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Profile",
                                              "AutoClicker_Profile.json", "JSON (*.json)")
        if path:
            try:
                with open(path, "w") as f:
                    json.dump(self._read_config(), f, indent=2)
            except Exception as e:
                logging.error(f"Export error: {e}")

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            skipped = []
            for k, v in data.items():
                if k in self.cfg:
                    self.cfg[k] = v
                else:
                    skipped.append(k)
            self._apply_config()
            msg = "Profile loaded."
            if skipped:
                msg += f"\nSkipped unknown keys: {', '.join(skipped)}"
            QMessageBox.information(self, "Profile Imported", msg)
        except Exception as e:
            logging.error(f"Import error: {e}")
            QMessageBox.warning(self, "Import Failed", str(e))


# ── Entry Point ────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AutoClicker")
    app.setQuitOnLastWindowClosed(False)

    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = False

    window = AutoClickerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
