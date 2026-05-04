# -*- mode: python ; coding: utf-8 -*-
"""ThaiVoice PyInstaller spec — onefile, windowed, with src/ layout."""

import os
import re

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# --- Paths ---
HERE = os.path.abspath(SPECPATH)                     # packaging/
ROOT = os.path.abspath(os.path.join(HERE, ".."))    # project root
SRC = os.path.join(ROOT, "src")

# --- Collect faster_whisper + ctranslate2 (they ship data files / DLLs) ---
fw_datas, fw_binaries, fw_hiddenimports = collect_all('faster_whisper')
ct2_datas, ct2_binaries, ct2_hiddenimports = collect_all('ctranslate2')

# Filter CUDA/GPU DLLs from ctranslate2 — app is CPU-only; CUDA adds ~30-60 MB
_CUDA_PREFIXES = re.compile(
    r'^(cublas|cudart|cudnn|cufft|nvrtc|curand|cusparse|cusolver|nvinfer'
    r'|nvjpeg|nvonnx|libnv)',
    re.IGNORECASE,
)

def _is_cuda_blob(path):
    return bool(_CUDA_PREFIXES.match(os.path.basename(path)))

ct2_binaries = [(s, d) for s, d in ct2_binaries if not _is_cuda_blob(s)]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT, SRC],
    binaries=[*fw_binaries, *ct2_binaries],
    datas=[
        (os.path.join(HERE, "icon.ico"), "."),  # bundled icon
        *fw_datas,
        *ct2_datas,
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
        *fw_hiddenimports,
        *ct2_hiddenimports,
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

# UPX must NOT compress .pyd files (Python extensions), pythonXXX.dll,
# ctranslate2/libiomp5md DLLs (CFG/security checks reject UPX-packed versions
# on some Windows 11 builds), or CRT api-ms-win-* shims.
_upx_exclude = [
    os.path.basename(b[0])
    for b in a.binaries
    if b[0].endswith('.pyd')
    or re.search(r'python\d+\.dll', b[0], re.IGNORECASE)
    or re.search(r'api-ms-win', b[0], re.IGNORECASE)
    or re.search(r'ctranslate2\.dll', b[0], re.IGNORECASE)
    or re.search(r'libiomp5md\.dll', b[0], re.IGNORECASE)
]

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
    upx_exclude=_upx_exclude,
    runtime_tmpdir=None,
    console=False,                  # --noconsole (windowed)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(HERE, "icon.ico"),
)
