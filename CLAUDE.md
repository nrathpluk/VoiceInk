# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ThaiVoice — Windows desktop app. Hotkey toggles mic recording → faster-whisper transcribes Thai → text copied to clipboard. Runs as floating capsule HUD (always-on-top, draggable, transparent corners via Tk `-transparentcolor`).

## Commands

```bat
pip install -r requirements.txt   :: install deps
python main.py                    :: run from source
run_debug.bat                     :: run with console + stderr → crash.log
build.bat                         :: build dist\ThaiVoice.exe (single-file)
build_installer.bat               :: build dist\ThaiVoice-Setup-0.1.0.exe (needs Inno Setup)
python make_icon.py               :: regen icon.ico
ruff check .                      :: lint
ruff format .                     :: format
python -m pytest                  :: run tests
pip install -r requirements-dev.txt :: install dev deps (ruff, pytest, pre-commit)
```

Tests in `tests/`. Run via `python -m pytest`.

`build.bat` auto-bootstraps UPX into `tools\upx\` on first run, kills any running `ThaiVoice.exe`, then runs PyInstaller via `ThaiVoice.spec`.

## Architecture

Multi-file layout (split from monolithic `main.py` per ROADMAP item 14):

| File | Role |
|---|---|
| `log_setup.py` | Stream guard + logging + excepthook. **MUST be first import** in `main.py` (before any 3rd-party). Exposes `log`, `LOG_PATH`. |
| `constants.py` | All app-wide constants (hotkey, models, languages, sample rate, window dims, colors, live-streaming timings, `TRANSPARENT_KEY`, `APP_NAME`). Pure data, no imports. |
| `util.py` | `State` enum, `toast`, `_resource_path`, Thai tokenizer (`_get_thai_tokenizer`, `_has_thai`, `insert_thai_word_breaks`). |
| `config.py` | Settings persistence — `_read_config` / `_write_config` to `%APPDATA%\ThaiVoice\config.json`. Atomic write via `.tmp` + `os.replace`. |
| `transcribe.py` | `load_whisper_model(name)` (with auto→cpu/int8 fallback) + `LiveTranscriber` (sliding-window streaming on top of faster-whisper). |
| `audio.py` | `AudioRecorder` — wraps `sd.InputStream`, computes RMS, owns recording buffer. Caller passes optional `on_frames` callback for live streaming. |
| `ui_capsule.py` | `FloatingWindow` — Tk `overrideredirect` window, custom-drawn pill on Canvas (rounded-rect via 2 rectangles + 4 ovals). Right-click menu, drag-to-move, transparent corners via `TRANSPARENT_KEY`. Uses `TYPE_CHECKING` forward ref for `App`. |
| `main.py` | `class App` — state machine (`State.IDLE/RECORDING/PROCESSING`), owns model, hotkey, history (`deque(maxlen=10)`), `AudioRecorder`, threading lock. `toggle()` is single entry point for hotkey + mic-button click. Plus `_main()` entry + `main()` fatal handler.

### Threading model

| Thread | Role |
|---|---|
| Main (Tk) | UI, mainloop, animation `after()` ticks |
| `keyboard` lib internal | Global hotkey hook (low-level Win API) |
| sounddevice callback | `AudioRecorder._cb` — appends frames, calls `on_frames` callback (which feeds live transcriber), computes RMS |
| `model-loader` | Loads `WhisperModel` async at startup; UI never blocks |
| `process` / `live-finalize` | One-shot transcribe per recording |
| `live-stream` | Periodic `LiveTranscriber.tick()` while live mode on |

Cross-thread UI updates **must** go through `App.ui(fn, *args)` which marshals via `root.after(0, ...)`. `threading.Lock` in `toggle()` guards against rapid hotkey mashing. Model load uses `threading.Event` (`model_ready`); `get_model()` blocks until set.

### Critical: PyInstaller `--noconsole` stream guard

`sys.stdout`/`sys.stderr` are **None** under `--noconsole`. Any third-party write (tqdm in faster-whisper, huggingface_hub progress bars) crashes silently. The block lives in `log_setup.py` and runs at module import time. `main.py` MUST have `from log_setup import log, LOG_PATH` as its first non-docstring statement, ABOVE every 3rd-party import (`numpy`, `pyperclip`, `keyboard`, `winotify`, `faster_whisper`, `tkinter`). Do not move 3rd-party imports above the `log_setup` import.

### Model load fallback chain

`load_whisper_model(name)` in `transcribe.py`: tries `WhisperModel(name, device="cpu", compute_type="int8")` first → on exception → `device="auto", compute_type="auto"`. CPU/int8 is the primary path because ctranslate2's CUDA init in frozen (PyInstaller) builds can trigger C-level crashes before Python's exception handler runs. Auto fallback enables GPU when available. `App._load_model_worker` calls `load_whisper_model` from a background thread; UI never blocks.

### Build (`ThaiVoice.spec`)

- `collect_all('faster_whisper')` + `collect_all('ctranslate2')` — both ship data files / DLLs PyInstaller can't autodetect.
- CUDA/GPU DLLs are filtered out post-collect via `_is_cuda_blob` (prefixes: `cublas`, `cudart`, `cudnn`, `cufft`, `nvrtc`, …). App is CPU-only by design; CUDA bits cost ~30–60 MB.
- UPX compresses everything **except** `.pyd` files (UPX corrupts Python ext modules), `pythonNNN.dll`, CRT/`api-ms-win-*` DLLs, `ctranslate2.dll`, and `libiomp5md.dll`. The last two are Intel C++ DLLs loaded via `ctypes.CDLL` by ctranslate2's `__init__.py`; UPX-compressed versions cause silent C-level crashes on Windows 11 when loaded this way even though UPX integrity test passes. See `_upx_exclude` (auto-populated from `a.binaries`).
- `excludes` strips deadweight stdlib/test packages.
- `hiddenimports=['winotify']` because `winotify` import is sometimes invisible to PyInstaller. (Local modules `log_setup`, `constants`, `util`, `config`, `audio`, `transcribe`, `ui_capsule` are direct imports of `main.py` — PyInstaller picks them up via the script entrypoint, so no hiddenimport entries needed.)

### Logging

`_resolve_log_dir()` (in `log_setup.py`) tries: exe/script dir → `%LOCALAPPDATA%\ThaiVoice` → `~`. Logs to `thai_voice.log`. `sys.excepthook` and `threading.excepthook` route uncaught exceptions there. Fatal `_main()` errors show a Tk messagebox pointing at the log path.

### Resource paths

Use `_resource_path(rel)` from `util.py` — handles both dev (`__file__` dir) and frozen (`sys._MEIPASS` temp dir from PyInstaller `--onefile`).

### Auto-update check

`updater.py` fetches `https://api.github.com/repos/{APP_REPO}/releases/latest` on startup in a daemon thread (`update-check`). Compared to `VERSION` in `constants.py` via `_normalize()` (lstrip `v`, split on `.`, integer parts). Toasts user if newer. Disabled via config `auto_update: false`. All network errors are logged and swallowed — never blocks UI or startup.

## Conventions

- All user-visible Thai strings are intentional — keep them Thai.
- Constants (window dims, colors, timings) live in `constants.py`. Edit there, not magic numbers inline.
- Toast errors via `toast(title, msg[:100])` — never re-raise in the UI thread; revert to `State.IDLE`.
- Cross-module imports follow the dependency tree: `log_setup` → `constants` → `util`/`config` → `audio`/`transcribe` → `ui_capsule` → `main`. Avoid back-imports; `ui_capsule` references `App` only under `TYPE_CHECKING`.
- DESIGN_NOTES.md documents *why* (faster-whisper, hotkey lib, sample rate, etc.). SHRINK_NOTES.md tracks size-reduction options for the .exe.
