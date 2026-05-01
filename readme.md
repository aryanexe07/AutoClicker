# AutoClicker

**Version:** 1.0.0

AutoClicker is a Windows desktop auto-clicker built in Python with a lightweight PyQt6 GUI. It supports cursor-following or fixed-coordinate clicking, multi-point sequences, configurable hotkeys, and several run modes for automation tasks.

---

## Features

- Left / Right / Middle mouse clicks
- Single, double, or triple click behaviour
- Interval configuration in hours, minutes, seconds, and milliseconds
- Fixed count and infinite repeat modes
- Timer-based stop after a duration
- Delay before starting the click sequence
- Follow-cursor or fixed XY click location
- Random coordinate offset for more natural click patterns
- Multi-point sequence support for repeated point-based workflows
- Preset modes for Web Monitor, Gaming (Fast), and Form Filling
- Global hotkeys for start/stop control
- Persistent configuration saved between launches

---

## Requirements

- Windows 10 or 11
- Python 3.10+

---

## Install

1. Open a terminal in the project root.
2. Install the dependencies:

```bash
pip install -r autoclicker/requirements.txt
```

---

## Run from source

From the project root:

```bash
python autoclicker/main.py
```

---

## Build a Windows executable

Install PyInstaller if needed:

```bash
pip install pyinstaller
```

Then build using the existing spec file:

```bash
cd autoclicker
pyinstaller build.spec
```

The generated executable will appear in the `dist/AutoClicker/` folder.

---

## Configuration

- Runtime settings are persisted in `autoclicker_config.json`.
- Settings include hotkeys, click interval, repeat mode, timer settings, random offset, and multi-point sequence data.
- When run from source, logs are written to `autoclicker.log` in the same folder.

---

## Hotkeys

- **Start:** `F6`
- **Stop:** `F7`

Hotkeys are handled globally so you can control clicking while the app is in the background.

---

## Testing

Run the unit tests with:

```bash
python -m unittest discover tests
```

The tests cover click behavior mapping, fixed coordinate clicks, and multi-point sequence logic.

---

## Project structure

- `autoclicker/main.py` — main application entry point and UI
- `autoclicker/core/clicker.py` — click execution and thread logic
- `autoclicker/core/settings.py` — persistent settings storage
- `autoclicker/requirements.txt` — required Python dependencies
- `autoclicker/build.spec` — PyInstaller build spec for packaging
- `tests/test_clicker.py` — automated unit tests

---

## Notes

- No admin privileges required
- Works offline
- The app is designed for Windows and uses PyQt6 for its GUI
- If a preset or saved configuration is invalid, the app falls back to default settings automatically
