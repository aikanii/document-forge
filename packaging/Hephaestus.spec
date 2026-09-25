# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Hephaestus — builds a desktop app.

Usage (from the project root):
    pyinstaller packaging/Hephaestus.spec --noconfirm

Produces dist/Hephaestus/ (one-folder build; faster startup than --onefile).
"""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent.parent          # project root
ASSETS = ROOT / "assets"

a = Analysis(
    [str(ROOT / "run_hephaestus.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ASSETS / "icon_64.png"), "assets"),
        (str(ASSETS / "icon_128.png"), "assets"),
        (str(ASSETS / "icon_256.png"), "assets"),
    ] + ([(str(ASSETS / "icon.ico"), "assets")]
         if (ASSETS / "icon.ico").exists() else []),
    hiddenimports=[
        "pymupdf", "fitz", "pypdf", "PIL", "pytesseract",
        "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
        "tkinter.font", "tkinter.colorchooser",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "pandas", "pytest", "IPython",
              "jupyter", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Hephaestus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                       # GUI app: no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "icon.ico") if sys.platform == "win32" else (
        str(ASSETS / "icon.icns") if (ASSETS / "icon.icns").exists() else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Hephaestus",
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Hephaestus.app",
        icon=str(ASSETS / "icon.icns") if (ASSETS / "icon.icns").exists() else None,
        bundle_identifier="ai.arena.hephaestus",
        version="1.0.0",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
            "NSHumanReadableCopyright": "Hephaestus — The Document Forge",
        },
    )
