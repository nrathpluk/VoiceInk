# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ThaiVoice — Windows desktop app. Hotkey toggles mic recording → faster-whisper transcribes Thai → text copied to clipboard. Runs as floating capsule HUD (always-on-top, draggable, transparent corners via Tk `-transparentcolor`). Single-file Python: all logic in `main.py`.

## Commands

```bat
pip install -r requirements.txt   :: install deps
python main.py                    :: run from source
run_debug.bat                     :: run with console + stderr → crash.log
build.bat                         :: build dist\ThaiVoice.exe (single-file)
python make_icon.py               :: regen icon.ico
```

No tests. No linter configured.

`build.bat` auto-bootstraps UPX into `tools\upx\` on first run, kills any running `ThaiVoice.exe`, then runs PyInstaller via `ThaiVoice.spec`.

## Architecture

Three Python classes in `main.py`:

- **`App`** — state machine (`State.IDLE/RECORDING/PROCESSING`), owns model, hotkey, history (`deque(maxlen=10)`), audio stream, threading lock. `toggle()` is the single entry point for hotkey + mic-button click.
- **`FloatingWindow`** — Tk `overrideredirect` window, custom-drawn pill on a Canvas (rounded-rect via 2 rectangles + 4 ovals). Right-click menu, drag-to-move, transparent corners by chroma-keying `TRANSPARENT_KEY = "#010203"`.
- **`LiveTranscriber`** — sliding-window streaming on top of faster-whisper. `feed()` accumulates audio; `tick()` re-transcribes uncommitted tail and commits segments older than `LIVE_COMMIT_TAIL_S` so they stop being recomputed.

### Threading model

| Thread | Role |
|---|---|
| Main (Tk) | UI, mainloop, animation `after()` ticks |
| `keyboard` lib internal | Global hotkey hook (low-level Win API) |
| sounddevice callback | `_audio_callback` — appends frames, feeds live transcriber, computes RMS |
| `model-loader` | Loads `WhisperModel` async at startup; UI never blocks |
| `process` / `live-finalize` | One-shot transcribe per recording |
| `live-stream` | Periodic `LiveTranscriber.tick()` while live mode on |

Cross-thread UI updates **must** go through `App.ui(fn, *args)` which marshals via `root.after(0, ...)`. `threading.Lock` in `toggle()` guards against rapid hotkey mashing. Model load uses `threading.Event` (`model_ready`); `get_model()` blocks until set.

### Critical: PyInstaller `--noconsole` stream guard

`sys.stdout`/`sys.stderr` are **None** under `--noconsole`. Any third-party write (tqdm in faster-whisper, huggingface_hub progress bars) crashes silently. The block at the top of `main.py` (lines 11–44) **must run before any 3rd-party import** — it redirects stdout/stderr to `thai_voice.stream.log`. Do not move imports above it.

### Model load fallback chain

`WhisperModel(name, device="auto", compute_type="auto")` → on exception → `device="cpu", compute_type="int8"`. Auto picks GPU+float16 when CUDA available, else CPU+float32. CPU/int8 fallback covers GPU OOM and missing CUDA DLLs (see DESIGN_NOTES §7).

### Build (`ThaiVoice.spec`)

- `collect_all('faster_whisper')` + `collect_all('ctranslate2')` — both ship data files / DLLs PyInstaller can't autodetect.
- CUDA/GPU DLLs are filtered out post-collect via `_is_cuda_blob` (prefixes: `cublas`, `cudart`, `cudnn`, `cufft`, `nvrtc`, …). App is CPU-only by design; CUDA bits cost ~30–60 MB.
- UPX compresses everything **except** `.pyd` files (UPX corrupts Python ext modules), `pythonNNN.dll`, and CRT/`api-ms-win-*` DLLs — see `_upx_exclude` build (auto-populated from `a.binaries`).
- `excludes` strips deadweight stdlib/test packages.
- `hiddenimports=['winotify']` because `winotify` import is sometimes invisible to PyInstaller.

### Logging

`_resolve_log_dir()` tries: exe/script dir → `%LOCALAPPDATA%\ThaiVoice` → `~`. Logs to `thai_voice.log`. `sys.excepthook` and `threading.excepthook` route uncaught exceptions there. Fatal `_main()` errors show a Tk messagebox pointing at the log path.

### Resource paths

Use `_resource_path(rel)` — handles both dev (`__file__` dir) and frozen (`sys._MEIPASS` temp dir from PyInstaller `--onefile`).

## Conventions

- All user-visible Thai strings are intentional — keep them Thai.
- Constants (window dims, colors, timings) live at top of `main.py`. Edit there, not magic numbers inline.
- Toast errors via `toast(title, msg[:100])` — never re-raise in the UI thread; revert to `State.IDLE`.
- DESIGN_NOTES.md documents *why* (faster-whisper, hotkey lib, sample rate, etc.). SHRINK_NOTES.md tracks size-reduction options for the .exe.
