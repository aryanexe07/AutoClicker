# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSFixedFileInfo,
    VSVersionInfo,
)


project_dir = Path(SPECPATH)
icon_path = str(project_dir / "assets" / "icon.ico")

version_info = VSVersionInfo(
    ffi=VSFixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "AutoClicker"),
                        StringStruct("FileDescription", "Auto Clicker"),
                        StringStruct("FileVersion", "1.0.0"),
                        StringStruct("InternalName", "AutoClicker"),
                        StringStruct("OriginalFilename", "AutoClicker.exe"),
                        StringStruct("ProductName", "AutoClicker"),
                        StringStruct("ProductVersion", "1.0.0"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[(icon_path, "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AutoClicker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version=version_info,
)
