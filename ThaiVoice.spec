# -*- mode: python ; coding: utf-8 -*-
# Slim build: drop CUDA DLLs (#2) + UPX (#1) + exclude deadweight (#4)
import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['winotify']

# Bundle icon for tkinter window (sys._MEIPASS at runtime)
if os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))

for pkg in ('faster_whisper', 'ctranslate2'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h


# --- CUDA / GPU DLL filter (we always run CPU) ---
_BAD_PREFIXES = (
    'cublas', 'cudart', 'cudnn', 'cufft', 'curand',
    'cusolver', 'cusparse', 'nvrtc', 'nvjit', 'nvtoolsext',
    'cupti', 'cufile', 'nvinfer', 'nvblas', 'nccl',
)


def _is_cuda_blob(item):
    name = os.path.basename(item[0]).lower()
    if any(name.startswith(p) for p in _BAD_PREFIXES):
        return True
    if 'cuda' in name and (name.endswith('.dll') or name.endswith('.so')):
        return True
    return False


binaries = [b for b in binaries if not _is_cuda_blob(b)]
datas = [d for d in datas if not _is_cuda_blob(d)]


# --- Deadweight excludes ---
EXCLUDES = [
    'tkinter.test', 'unittest', 'pydoc_data', 'test',
    'distutils', 'lib2to3', 'turtle', 'turtledemo',
    'idlelib', 'ensurepip', 'pip', 'setuptools',
    'pytest', '_pytest', 'IPython', 'jupyter',
    'matplotlib', 'pandas', 'scipy',
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Auto-exclude every .pyd from UPX (UPX often errors on Python ext modules
# due to load-config / CFG quirks). Also exclude python forwarder DLL
# and core CRT DLLs.
_upx_exclude = [
    'vcruntime140.dll', 'vcruntime140_1.dll',
    'python314.dll', 'python313.dll', 'python312.dll',
    'python3.dll',
    'msvcp140.dll', 'msvcp140_1.dll',
    'api-ms-win-core-path-l1-1-0.dll',
]
for _bin in a.binaries:
    _name = os.path.basename(_bin[0])
    if _name.lower().endswith('.pyd'):
        _upx_exclude.append(_name)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ThaiVoice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=_upx_exclude,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
