# AutoClicker

A lightweight Python desktop auto clicker for Windows with a clean, minimal UI.

---

## Requirements

- Windows 10 or 11
- Python 3.10+

## Installation

```bash
pip install pyqt6 pyautogui pynput
```

---

## Running from source

```bash
python main.py
```

---

## Building the .exe

Make sure PyInstaller is installed:

```bash
pip install pyinstaller
```

Then run the included build script:

```bash
build.bat
```

This produces a single `AutoClicker.exe` inside the `dist/` folder. No Python installation required on the target machine.

> If you don't have an `icon.ico`, remove `--icon=icon.ico` from `build.bat` before running.

---

## Usage

| Feature | How to use |
|---|---|
| **Click type** | Choose Left / Right / Middle from the dropdown |
| **Single / Double** | Toggle the click behaviour radio button |
| **Click speed** | Enter a number and pick ms or seconds |
| **Location** | "Current position" follows your cursor. "Fixed" lets you type or pick coordinates |
| **Pick coordinates** | Click the Pick button, then click anywhere on screen |
| **Loop mode** | Infinite runs forever. Fixed count stops after N clicks |
| **Timer mode** | Check the box and set seconds to auto-stop after a duration |
| **Delay before start** | App counts down before clicking begins (default 3 s) |
| **Start / Stop** | Click the big button or use global hotkeys |
| **Hotkeys** | Default: F6 to start, F7 to stop. Click the hotkey field and press any key to change |

---

## Default hotkeys

| Action | Key |
|---|---|
| Start | F6 |
| Stop | F7 |

Hotkeys work even when the app is in the background.

---

## Settings

All settings are saved automatically when you close the app and restored on next launch (`autoclicker_config.json` in the same folder as the exe).

---

## Logs

Error are written to `autoclicker.log` in the same directory as the exe.

---

## Notes

- No admin privileges required
- Works entirely offline
- Minimum click interval: 10 ms
- Tested stable at 50 ms intervals over extended sessions