# -*- mode: python ; coding: utf-8 -*-
# Build with build_exe.bat  ->  dist\SpaceRouge\SpaceRouge.exe
# Set SR_CONSOLE=1 first to get a console window that shows crashes.
import os
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], ["_cffi_backend", "_miniaudio", "numpy"]
for pkg in ("tcod", "miniaudio"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# the game's own files (paths in the game are relative to the bundle folder)
datas += [
    ("story1.txt", "."),
    ("story2.txt", "."),
    ("title.txt", "."),
    ("Haberdash_curses_12x12.png", "."),
    ("music_levels.json", "."),
    ("assets", "assets"),
    ("sfx", "sfx"),
]

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="SpaceRouge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=os.environ.get("SR_CONSOLE") == "1",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SpaceRouge",
)
