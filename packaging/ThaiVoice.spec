# -*- mode: python ; coding: utf-8 -*-
"""ThaiVoice PyInstaller spec — onefile, windowed, with src/ layout."""

import os

block_cipher = None

# --- Paths ---
HERE = os.path.abspath(os.path.dirname(SPECPATH))   # packaging/
ROOT = os.path.abspath(os.path.join(HERE, ".."))    # project root
SRC = os.path.join(ROOT, "src")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT, SRC],
    binaries=[],
    datas=[
        (os.path.join(HERE, "icon.ico"), "."),  # bundled icon
    ],
    hiddenimports=[
        # Local package modules — PyInstaller sometimes misses them
        "app",
        "app.main",
        "app.core.constants",
        "app.core.config",
        "app.utils.log_setup",
        "app.utils.util",
        "app.services.audio",
        "app.services.transcribe",
        "app.services.updater",
        "app.ui.ui_capsule",
        # 3rd-party that may be lazy-loaded or missed
        "sounddevice",
        "keyboard",
        "pyperclip",
        "winotify",
        "numpy",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "tokenizers",
        "pythainlp",
        "pythainlp.tokenize",
        # sounddevice backend
        "_sounddevice_data",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude CUDA libs to keep the build slim (CPU-only)
        "torch", "torchvision", "torchaudio",
        "nvidia", "triton",
        "tensorrt",
        # Heavy / unused stdlib
        "test", "unittest",
        "pydoc", "doctest",
        "lib2to3",
        "distutils",
        "setuptools",
        "pip",
        "ensurepip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ThaiVoice",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # --noconsole (windowed)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(HERE, "icon.ico"),
)
