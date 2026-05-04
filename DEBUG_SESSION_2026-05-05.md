# ThaiVoice EXE Crash Debug Session — 2026-05-05

## Problem

`dist\ThaiVoice.exe` would not open. No error dialog. No Python exception in log.
App worked fine from source (`python main.py`).

---

## Crash Pattern (from `thai_voice.log`)

Every run ended at the same point:

```
INFO  model-loader Loading model 'small' (device=auto)
DEBUG model-loader connect_tcp.started ...
DEBUG model-loader receive_response_headers.complete ... HTTP/1.1 200 OK
INFO  model-loader HTTP Request: GET huggingface.co/.../revision/main 200 OK
DEBUG model-loader response_closed.complete
(nothing more — process dead)
```

The crash happened **after** the HuggingFace metadata check, **before** `Model loaded` was ever logged. No Python exception. No traceback. No exit log.

---

## Investigation

### Step 1 — Identify crash is C-level

Python's `sys.excepthook` and `threading.excepthook` were installed in `log_setup.py`. Neither fired. This means the crash was **below Python** — a native C/C++ fault that bypassed all Python error handling.

### Step 2 — Narrow crash location

Added STEP markers to `load_whisper_model` in `transcribe.py`:

```python
log.info("STEP1: calling WhisperModel(%r, cpu, int8)", name)
m = WhisperModel(name, device="cpu", compute_type="int8")
log.info("STEP2: WhisperModel created OK")
```

Goal: if STEP1 appears but not STEP2 → crash is inside `ctranslate2.models.Whisper()`.

### Step 3 — New crash discovered (wrong direction)

Added `os.dup2` to `log_setup.py` to redirect C-level fd 2 to a file (to capture ctranslate2 native output). This **introduced a new crash** — EXE now died before even logging `python=3.14.4`.

Reverted `os.dup2`. But then EXE still crashed before `python=3.14.4`, even earlier than before.

### Step 4 — Root cause: UPX compression of ctranslate2.dll

Checked PyInstaller UPX bincache:

```
bincache01py31464bit/ctranslate2/
  ctranslate2.dll   17 MB  (compressed from 57 MB)
  libiomp5md.dll   567 KB  (compressed from 1.6 MB)
```

UPX integrity test said both files were `[OK]`. But the crash was happening at **import time**, before any Python code after `log_setup.py` ran.

**Key insight:** `ctranslate2/__init__.py` does this:

```python
for library in glob.glob(os.path.join(package_dir, "*.dll")):
    ctypes.CDLL(library)   # ← no try/except
```

It loads every `.dll` in its package directory via `ctypes.CDLL()` at import time.  
`ctypes.CDLL()` is a different DLL load path from normal Windows `LoadLibrary`.  
**UPX-packed DLLs loaded this way crash at C level on Windows 11** — even though the UPX self-test passes.

### Step 5 — Verify fix

Added `ctranslate2.dll` and `libiomp5md.dll` to `_upx_exclude` in `ThaiVoice.spec`:

```python
_upx_exclude = [
    os.path.basename(b[0])
    for b in a.binaries
    if b[0].endswith('.pyd')
    or re.search(r'python\d+\.dll', b[0], re.IGNORECASE)
    or re.search(r'api-ms-win', b[0], re.IGNORECASE)
    or re.search(r'ctranslate2\.dll', b[0], re.IGNORECASE)   # ← new
    or re.search(r'libiomp5md\.dll', b[0], re.IGNORECASE)    # ← new
]
```

Rebuilt. Result:

```
INFO model-loader Model loaded: device=cpu compute=int8
```

EXE running stable. 490 MB memory (model in RAM). ✓

---

## Other Bugs Fixed Along the Way

### Bug 2 — PyInstaller SPECPATH wrong in spec file

**Symptom:** `ERROR: script 'C:\Users\JAY\Desktop\spaek_andcopy\main.py' not found`

**Cause:** In PyInstaller 6.x, `SPECPATH` is already a directory path. The spec had:

```python
HERE = os.path.abspath(os.path.dirname(SPECPATH))  # wrong — goes up one level too many
```

**Fix:**
```python
HERE = os.path.abspath(SPECPATH)  # SPECPATH is already the packaging/ directory
```

### Bug 3 — CUDA init crash in frozen build

**Symptom:** Even with correct spec and UPX fix, earlier test builds crashed after HF check.

**Cause:** `device="auto"` makes ctranslate2 attempt CUDA device detection before falling back to CPU. In a frozen PyInstaller build, CUDA initialization can crash at C level before Python's exception handler can intercept it.

**Fix:** Flip load order in `load_whisper_model` — try CPU first, fall back to auto:

```python
try:
    m = WhisperModel(name, device="cpu", compute_type="int8")
    log.info("Model loaded: device=cpu compute=int8")
    return m
except Exception as e:
    log.warning("cpu/int8 load failed: %s — retry auto", e)
    m = WhisperModel(name, device="auto", compute_type="auto")
    log.info("Model loaded: device=auto compute=auto")
    return m
```

### Bug 4 — collect_all missing from spec

**Cause:** Original spec used only `hiddenimports` for ctranslate2 and faster_whisper. These libraries ship native DLLs and data files that PyInstaller cannot autodetect from Python import analysis alone.

**Fix:** Use `collect_all()` for both:

```python
fw_datas, fw_binaries, fw_hiddenimports = collect_all('faster_whisper')
ct2_datas, ct2_binaries, ct2_hiddenimports = collect_all('ctranslate2')
```

Also filter CUDA DLLs post-collect (app is CPU-only, CUDA adds 30–60 MB):

```python
_CUDA_PREFIXES = re.compile(
    r'^(cublas|cudart|cudnn|cufft|nvrtc|curand|cusparse|cusolver|nvinfer|nvjpeg|nvonnx|libnv)',
    re.IGNORECASE,
)
ct2_binaries = [(s, d) for s, d in ct2_binaries if not _is_cuda_blob(s)]
```

---

## Files Changed

| File | Change |
|---|---|
| `packaging/ThaiVoice.spec` | SPECPATH fix; `collect_all`; CUDA DLL filter; UPX exclusions for ctranslate2.dll + libiomp5md.dll |
| `src/app/services/transcribe.py` | `load_whisper_model`: cpu-first with auto fallback; log ct2 version |
| `CLAUDE.md` | Updated Build section; updated Model load fallback chain description |

---

## Key Takeaway

> **UPX must not compress DLLs that are loaded via `ctypes.CDLL()` at import time.**  
> These bypass normal Windows DLL loading and the UPX self-decompression stub misbehaves.  
> `ctranslate2.dll` and `libiomp5md.dll` both fall into this category.  
> Add them explicitly to `upx_exclude` in any PyInstaller spec that bundles ctranslate2.
