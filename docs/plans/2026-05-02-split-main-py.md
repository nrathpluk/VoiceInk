# Split main.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolithic `main.py` (1141 lines) into focused modules without changing runtime behavior.

**Architecture:** Pure mechanical extraction. No new abstractions, no behavior changes. Move code blocks into 6 new modules; `main.py` keeps only `App` class + entry point. Stream-guard+logging block stays first import (CLAUDE.md requirement). Use `TYPE_CHECKING` for `FloatingWindow → App` type hint to avoid circular import.

**Tech Stack:** Python 3, Tk, faster-whisper, sounddevice, keyboard, pyperclip, winotify, numpy, pythainlp.

**Repo state:** Not a git repo, no tests. Verification = manual smoke test after each task: `python main.py` → hotkey toggles record → text copied to clipboard. No `git commit` steps; "checkpoint" = save + run + verify.

**Critical invariants (must NOT break):**
- Stream guard (`sys.stdout`/`sys.stderr` redirect) runs **before any 3rd-party import**.
- `logging.basicConfig` runs once, before any `log.info`/`log.exception`.
- `sys.excepthook` and `threading.excepthook` set early.
- All cross-thread UI updates go through `App.ui(fn, *args)` which marshals via `root.after(0, ...)`.
- `WhisperModel` load fallback: `device="auto",compute_type="auto"` → on exception → `device="cpu",compute_type="int8"`.
- `_resource_path()` works under both dev and PyInstaller `--onefile` (`sys._MEIPASS`).
- All Thai user-visible strings stay Thai.

---

## File Structure

| File | Lines (approx) | Responsibility |
|---|---|---|
| `log_setup.py` | ~80 | `_resolve_log_dir`, stream guard, `logging.basicConfig`, excepthooks. Exposes `log`, `LOG_PATH`. Imports only stdlib. |
| `constants.py` | ~50 | All module-level constants: hotkey, models, languages, sample rate, window dims, colors, live-streaming timings, `TRANSPARENT_KEY`, `APP_NAME`. |
| `util.py` | ~70 | `_resource_path`, `_has_thai`, `_get_thai_tokenizer`, `insert_thai_word_breaks`, `State` enum, `toast`. |
| `transcribe.py` | ~120 | `load_whisper_model(name) -> WhisperModel` (with CPU/int8 fallback) + `LiveTranscriber`. |
| `audio.py` | ~50 | `AudioRecorder` — wraps `sd.InputStream`, computes RMS, exposes `start(on_frames, on_rms)` / `stop() -> np.ndarray`. |
| `ui_capsule.py` | ~370 | `FloatingWindow` class verbatim. Uses `TYPE_CHECKING` for `App` type hint. |
| `main.py` | ~250 | `App` class + `_main()` + `main()` + `if __name__ == "__main__"` block. Imports `log_setup` first. |

---

## Task 1: Baseline smoke test + reference output

**Files:**
- Read: `main.py` (current behavior)

- [ ] **Step 1: Verify current `main.py` runs**

Run: `python main.py`
Expected: Capsule window appears bottom-right. No console errors.

- [ ] **Step 2: Smoke test record path**

1. Press `Ctrl+Shift+Space` → wait for model load if first time → speak Thai briefly → press hotkey again.
2. Expected: Text copied to clipboard (paste into Notepad to confirm). Toast notification "Copied".

- [ ] **Step 3: Smoke test live mode**

1. Right-click capsule → enable Live mode.
2. Press hotkey → speak → press hotkey.
3. Expected: Preview text appears, clipboard has finalized text.

- [ ] **Step 4: Save baseline log**

Run: `copy thai_voice.log thai_voice.log.baseline`
Expected: file copied. Used as reference if regressions appear.

- [ ] **Step 5: Checkpoint**

```
backup main.py:  copy main.py main.py.original
```
Confirms rollback option exists. Keep `main.py.original` until task 9 succeeds.

---

## Task 2: Create `log_setup.py`

**Files:**
- Create: `log_setup.py`
- Modify: `main.py` (replace lines 1-94 with import)

- [ ] **Step 1: Create `log_setup.py` with full stream-guard + logging block**

Content (verbatim from `main.py:1-75`, adapted to be importable):

```python
"""Log + stream guard. MUST be first import in main.py.

Under PyInstaller --noconsole, sys.stdout/sys.stderr are None. Any 3rd-party
write (tqdm in faster-whisper, hf_hub) crashes silently. Redirect early.
"""
import logging
import os
import sys
import threading
import traceback


def _resolve_log_dir():
    if getattr(sys, "frozen", False):
        primary = os.path.dirname(sys.executable)
    else:
        primary = os.path.dirname(os.path.abspath(__file__))
    for candidate in (primary,
                      os.path.join(os.environ.get("LOCALAPPDATA",
                                                  os.path.expanduser("~")),
                                   "ThaiVoice"),
                      os.path.expanduser("~")):
        try:
            os.makedirs(candidate, exist_ok=True)
            test = os.path.join(candidate, ".thai_voice_write_test")
            with open(test, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(test)
            return candidate
        except Exception:
            continue
    return os.getcwd()


_LOG_DIR = _resolve_log_dir()
LOG_PATH = os.path.join(_LOG_DIR, "thai_voice.log")
_STREAM_PATH = os.path.join(_LOG_DIR, "thai_voice.stream.log")

if sys.stdout is None or getattr(sys.stdout, "fileno", None) is None:
    sys.stdout = open(_STREAM_PATH, "a", encoding="utf-8", buffering=1)
if sys.stderr is None or getattr(sys.stderr, "fileno", None) is None:
    sys.stderr = sys.stdout

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("thaivoice")


def _excepthook(exc_type, exc_value, exc_tb):
    log.error("UNCAUGHT: %s",
              "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


sys.excepthook = _excepthook
try:
    threading.excepthook = lambda args: log.error(
        "THREAD UNCAUGHT in %s: %s", args.thread.name,
        "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
except Exception:
    pass

log.info("=== ThaiVoice start. log=%s ===", LOG_PATH)
```

- [ ] **Step 2: Replace lines 1-94 in `main.py` with single import**

Top of `main.py` (replacing the old block):

```python
"""Thai Voice -> Clipboard. Floating capsule window. Hotkey toggles record."""
# log_setup MUST be first — installs stream guard + logging before any 3rd-party import.
from log_setup import log, LOG_PATH  # noqa: F401  (LOG_PATH used in error UI)

import math
import os
import re
import sys
import threading
from collections import deque
from enum import Enum

import tkinter as tk  # noqa: E402
from tkinter import messagebox, simpledialog  # noqa: E402

import numpy as np
import pyperclip
import sounddevice as sd

try:
    import keyboard
except ImportError:
    print("keyboard lib missing. pip install keyboard", file=sys.stderr)
    raise

try:
    from winotify import Notification
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False

from faster_whisper import WhisperModel
```

(Note: `traceback`, `logging`, `_excepthook` removed from `main.py` — moved into `log_setup.py`.)

- [ ] **Step 3: Run smoke test**

Run: `python main.py`
Expected: Same as Task 1 step 1. Window appears. `thai_voice.log` shows new "=== ThaiVoice start ===" line.

- [ ] **Step 4: Verify stream-guard ordering**

Open `log_setup.py` and `main.py` side-by-side. Confirm `from log_setup import ...` is the FIRST non-docstring statement in `main.py` and is above all 3rd-party imports.

- [ ] **Step 5: Checkpoint**

Smoke test record path (Task 1 step 2). If passes, proceed.

---

## Task 3: Create `constants.py`

**Files:**
- Create: `constants.py`
- Modify: `main.py` (remove constants block, add import)

- [ ] **Step 1: Create `constants.py`**

Content (verbatim from `main.py:96-140`):

```python
"""App-wide constants. No imports beyond stdlib."""

DEFAULT_HOTKEY = "ctrl+shift+space"
DEFAULT_MODEL = "base"
MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_LANGUAGE = "th"
LANGUAGES = ["auto", "th", "en"]
LANGUAGE_LABELS = {"auto": "Auto-detect", "th": "ไทย (Thai)", "en": "English"}
SAMPLE_RATE = 16000
HISTORY_MAX = 10
APP_NAME = "ThaiVoice"

WIN_W = 320
WIN_H = 64

WAVE_BARS = 10
WAVE_BAR_W = 3
WAVE_BAR_GAP = 4

CAPSULE_RADIUS = 30
MIC_R = 26
MIC_CX = 36
MIC_CY = WIN_H // 2

# Live streaming
LIVE_WINDOW_S = 8.0
LIVE_TICK_S = 1.5
LIVE_COMMIT_TAIL_S = 3.0
LIVE_PREVIEW_H = 76

# Chroma key for transparent corners (overrideredirect + transparentcolor)
TRANSPARENT_KEY = "#010203"

COLORS = {
    "bg": "#1a1a2e",
    "fg": "#e8e8ea",
    "muted": "#8a8a92",
    "wave_idle": "#4a4a6a",
    "wave_active": "#6C63FF",
    "purple": "#6C63FF",
    "red": "#FF4444",
    "green": "#2ECC71",
    "menu_dot": "#5a5a72",
    "glow": "#2a1d4a",
    "preview_bg": "#15151f",
}
```

- [ ] **Step 2: In `main.py`, remove lines that defined those constants**

Delete the original constants block. Add this import after the stdlib imports:

```python
from constants import (
    DEFAULT_HOTKEY, DEFAULT_MODEL, MODELS, DEFAULT_LANGUAGE,
    LANGUAGES, LANGUAGE_LABELS, SAMPLE_RATE, HISTORY_MAX, APP_NAME,
    WIN_W, WIN_H, WAVE_BARS, WAVE_BAR_W, WAVE_BAR_GAP,
    CAPSULE_RADIUS, MIC_R, MIC_CX, MIC_CY,
    LIVE_WINDOW_S, LIVE_TICK_S, LIVE_COMMIT_TAIL_S, LIVE_PREVIEW_H,
    TRANSPARENT_KEY, COLORS,
)
```

- [ ] **Step 3: Smoke test**

Run: `python main.py`
Expected: Window appears with same dimensions and colors as before.

- [ ] **Step 4: Verify by visual diff**

Resize comparison: capsule width 320, height 64 (or 140 with live mode). Colors match (purple `#6C63FF` accent, dark `#1a1a2e` background). If anything looks off, re-check imports.

- [ ] **Step 5: Checkpoint**

Smoke test record path. Pass → proceed.

---

## Task 4: Create `util.py`

**Files:**
- Create: `util.py`
- Modify: `main.py` (remove utility funcs, add import)

- [ ] **Step 1: Create `util.py`**

Content (extracted from `main.py:143-210`):

```python
"""Small helpers: Thai tokenizer, resource path, State enum, toast."""
import os
import re
import sys
from enum import Enum

from log_setup import log
from constants import APP_NAME

try:
    from winotify import Notification
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False


_thai_tokenize_fn = None
_thai_tokenize_failed = False


def _get_thai_tokenizer():
    """Lazy-load pythainlp.word_tokenize. Cache success/failure."""
    global _thai_tokenize_fn, _thai_tokenize_failed
    if _thai_tokenize_fn is not None or _thai_tokenize_failed:
        return _thai_tokenize_fn
    try:
        from pythainlp.tokenize import word_tokenize  # type: ignore
        _thai_tokenize_fn = word_tokenize
        log.info("pythainlp tokenizer loaded")
    except Exception as e:
        log.warning("pythainlp not available: %s", e)
        _thai_tokenize_failed = True
    return _thai_tokenize_fn


_THAI_RANGE = (0x0E00, 0x0E7F)


def _has_thai(s: str) -> bool:
    return any(_THAI_RANGE[0] <= ord(c) <= _THAI_RANGE[1] for c in s)


def insert_thai_word_breaks(text: str) -> str:
    """Insert spaces between Thai word tokens. Non-Thai segments untouched."""
    if not text or not _has_thai(text):
        return text
    fn = _get_thai_tokenizer()
    if fn is None:
        return text
    try:
        toks = fn(text, engine="newmm", keep_whitespace=False)
        joined = " ".join(t for t in toks if t)
        return re.sub(r"\s+", " ", joined).strip()
    except Exception:
        log.exception("thai tokenize failed")
        return text


def _resource_path(rel: str) -> str:
    """Locate bundled resource. Works in dev + PyInstaller frozen."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


def toast(title: str, msg: str):
    if not HAS_TOAST:
        return
    try:
        Notification(app_id=APP_NAME, title=title, msg=msg).show()
    except Exception:
        pass
```

**Note on `_resource_path`:** In `util.py`, `__file__` resolves to `util.py`'s own dir. Since all source files now live in the same dir as `main.py`, this still resolves to the project root. PyInstaller `sys._MEIPASS` path is unchanged. Verified safe.

- [ ] **Step 2: In `main.py`, remove utility funcs**

Delete lines defining `_get_thai_tokenizer`, `_THAI_RANGE`, `_has_thai`, `insert_thai_word_breaks`, `_resource_path`, `State`, `toast`, and the `winotify`/`HAS_TOAST` import block (now in `util.py`).

Add import:

```python
from util import (
    _resource_path, _has_thai, _get_thai_tokenizer, insert_thai_word_breaks,
    State, toast,
)
```

- [ ] **Step 3: Smoke test**

Run: `python main.py`
Expected: Window appears. Right-click → menu shows correctly. Toast notifications fire on actions (e.g., toggle live mode → "Live mode: ON" toast).

- [ ] **Step 4: Test Thai tokenizer path**

Record short Thai phrase. Verify clipboard text has spaces between Thai words (only if `tokenize_thai` is on, default true).

- [ ] **Step 5: Checkpoint**

Pass → proceed.

---

## Task 5: Create `transcribe.py`

**Files:**
- Create: `transcribe.py`
- Modify: `main.py` (remove `LiveTranscriber`, extract model loader; add imports)

- [ ] **Step 1: Create `transcribe.py`**

```python
"""WhisperModel loader + sliding-window streaming transcriber."""
import threading
import numpy as np
from faster_whisper import WhisperModel

from log_setup import log
from constants import SAMPLE_RATE, LIVE_WINDOW_S, LIVE_COMMIT_TAIL_S


def load_whisper_model(name: str) -> WhisperModel:
    """Load WhisperModel with auto→cpu/int8 fallback. Raises on total failure.

    Auto picks GPU+float16 when CUDA available, else CPU+float32.
    CPU/int8 fallback covers GPU OOM and missing CUDA DLLs.
    """
    try:
        m = WhisperModel(name, device="auto", compute_type="auto")
        log.info("Model loaded: device=auto compute=auto")
        return m
    except Exception as e:
        log.warning("auto load failed: %s — retry CPU/int8", e)
        m = WhisperModel(name, device="cpu", compute_type="int8")
        log.info("Model loaded: device=cpu compute=int8")
        return m


class LiveTranscriber:
    """Sliding-window streaming on top of faster-whisper.

    feed() collects float32 audio; tick() re-transcribes the uncommitted
    tail (last LIVE_WINDOW_S), commits segments older than LIVE_COMMIT_TAIL_S
    so they stop being recomputed, and exposes (committed, tentative) text.
    """

    def __init__(self, model: WhisperModel, sample_rate: int = SAMPLE_RATE,
                 language: str | None = "th"):
        self.model = model
        self.sr = sample_rate
        self.language = language
        self.committed = ""
        self.tentative = ""
        self.committed_samples = 0
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()

    def feed(self, chunk: np.ndarray):
        with self._lock:
            self._chunks.append(chunk.copy())

    def _uncommitted_audio(self) -> np.ndarray:
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            full = np.concatenate(self._chunks, axis=0).flatten().astype(np.float32)
        return full[self.committed_samples:]

    def tick(self, final: bool = False):
        """Re-transcribe pending tail. final=True commits everything."""
        audio = self._uncommitted_audio()
        if audio.size < self.sr * 0.6:
            return
        max_samples = int(self.sr * LIVE_WINDOW_S)
        offset_in_full = 0
        if not final and audio.size > max_samples:
            offset_in_full = audio.size - max_samples
            audio = audio[offset_in_full:]

        try:
            lang = None if self.language in (None, "auto") else self.language
            segs, _ = self.model.transcribe(
                audio,
                language=lang,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                condition_on_previous_text=False,
            )
            seg_list = list(segs)
        except Exception:
            log.exception("live transcribe failed")
            return

        cutoff_s = (audio.size / self.sr) - LIVE_COMMIT_TAIL_S
        commit_text = ""
        commit_end_s = 0.0
        tail_text = ""
        for s in seg_list:
            t = (s.text or "").strip()
            if not t:
                continue
            if final or s.end <= cutoff_s:
                commit_text += (" " if commit_text and not commit_text.endswith(" ") else "") + t
                commit_end_s = s.end
            else:
                tail_text += (" " if tail_text else "") + t

        if commit_text:
            sep = "" if not self.committed or self.committed.endswith(" ") else " "
            self.committed = (self.committed + sep + commit_text).strip()
            commit_samples = int(commit_end_s * self.sr) + offset_in_full
            self.committed_samples += commit_samples
        self.tentative = tail_text if not final else ""

    def full_text(self) -> str:
        if self.tentative:
            return (self.committed + " " + self.tentative).strip()
        return self.committed
```

- [ ] **Step 2: Replace `App._load_model_worker` body to use `load_whisper_model`**

In `main.py`, change `_load_model_worker` to:

```python
def _load_model_worker(self):
    name = self.model_name
    log.info("Loading model %r (device=auto)", name)
    toast(APP_NAME, f"Loading model '{name}'...")
    loaded: WhisperModel | None = None
    err: Exception | None = None
    try:
        loaded = load_whisper_model(name)
    except Exception as e:
        log.exception("Model load failed (cpu fallback also failed)")
        err = e
    if loaded is not None:
        self.model = loaded
        self.model_error = None
        self.model_ready.set()
        self.ui(self._on_model_loaded)
    else:
        self.model = None
        self.model_error = err
        self.model_ready.set()
        self.ui(self._on_model_load_failed, err)
```

- [ ] **Step 3: In `main.py`, remove `LiveTranscriber` class**

Delete lines 587-669 (whole class block). Replace `from faster_whisper import WhisperModel` line — keep it (App still type-hints `WhisperModel`) AND add:

```python
from transcribe import LiveTranscriber, load_whisper_model
```

- [ ] **Step 4: Smoke test**

Run: `python main.py`
Expected: Window appears, model loads (watch log for "Model loaded: device=...").

- [ ] **Step 5: Smoke test live mode end-to-end**

Enable Live mode → record → speak → stop. Verify preview updates and clipboard has finalized text.

- [ ] **Step 6: Checkpoint**

Pass → proceed.

---

## Task 6: Create `audio.py`

**Files:**
- Create: `audio.py`
- Modify: `main.py` (replace `_audio_callback` + `start_record` + `stop_record` with `AudioRecorder` usage)

- [ ] **Step 1: Create `audio.py`**

```python
"""Mic recording wrapper around sounddevice.

AudioRecorder owns the sd.InputStream. Caller supplies callbacks for
per-chunk frame data and RMS updates. stop() returns the concatenated
float32 buffer.
"""
from typing import Callable, Optional
import numpy as np
import sounddevice as sd

from log_setup import log
from constants import SAMPLE_RATE


class AudioRecorder:
    def __init__(self):
        self.stream: Optional[sd.InputStream] = None
        self.frames: list[np.ndarray] = []
        self.current_rms: float = 0.0
        self._on_frames: Optional[Callable[[np.ndarray], None]] = None

    def start(self, on_frames: Optional[Callable[[np.ndarray], None]] = None):
        """Start mic stream. on_frames(chunk_float32_flat) called per callback.

        Raises if no input device found.
        """
        self.frames = []
        self.current_rms = 0.0
        self._on_frames = on_frames
        sd.query_devices(kind="input")  # raises if no mic
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._cb,
        )
        self.stream.start()

    def _cb(self, indata, frames, time_info, status):
        if status:
            pass
        self.frames.append(indata.copy())
        if self._on_frames is not None:
            try:
                self._on_frames(indata.flatten().astype(np.float32))
            except Exception:
                log.exception("on_frames callback failed")
        try:
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            self.current_rms = rms
        except Exception:
            pass

    def stop(self) -> np.ndarray:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.current_rms = 0.0
        if not self.frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self.frames, axis=0).flatten().astype(np.float32)

    def force_close(self):
        """Best-effort cleanup for quit path. No raise."""
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None
```

- [ ] **Step 2: Wire `AudioRecorder` into `App.__init__`**

In `main.py`, inside `App.__init__`, replace:

```python
self.recording_frames: list = []
self.stream = None
...
self.current_rms = 0.0
```

with:

```python
self.audio = AudioRecorder()
```

Add at top of `main.py`:

```python
from audio import AudioRecorder
```

Remove `import sounddevice as sd` (now only in `audio.py`).

- [ ] **Step 3: Replace `App._audio_callback`, `start_record`, `stop_record`**

Delete those three methods (lines 825-861). Update existing call sites:

`App.toggle()` — replace `self.start_record()` with:

```python
def _on_audio_chunk(chunk):
    if self.live is not None:
        self.live.feed(chunk)
self.audio.start(on_frames=_on_audio_chunk)
```

And replace `self.stop_record()` with `self.audio.stop()`.

In `App._wave_tick`, replace `rms = self.current_rms` with `rms = self.audio.current_rms`.

In `App.quit`, replace the `self.stream` cleanup block with:

```python
self.audio.force_close()
```

- [ ] **Step 4: Smoke test record path**

Run: `python main.py` → hotkey → speak Thai → hotkey.
Expected: Clipboard has transcribed text. Waveform animates while recording.

- [ ] **Step 5: Smoke test no-mic path**

Disable default mic in Windows sound settings → press hotkey.
Expected: Toast "No mic ..." appears. App stays in IDLE state. Re-enable mic and try again — should work.

- [ ] **Step 6: Smoke test live mode**

Enable Live mode → record → confirm `live.feed()` still receives chunks (preview updates).

- [ ] **Step 7: Checkpoint**

Pass → proceed.

---

## Task 7: Create `ui_capsule.py`

**Files:**
- Create: `ui_capsule.py`
- Modify: `main.py` (remove `FloatingWindow` class, add import)

- [ ] **Step 1: Create `ui_capsule.py` with full `FloatingWindow` body**

Header (top of file):

```python
"""Floating capsule HUD window. Custom-drawn pill on Tk Canvas."""
from __future__ import annotations
import math
import os
import tkinter as tk
from typing import TYPE_CHECKING

from log_setup import log
from constants import (
    APP_NAME, WIN_W, WIN_H, WAVE_BARS, WAVE_BAR_W, WAVE_BAR_GAP,
    CAPSULE_RADIUS, MIC_R, MIC_CX, MIC_CY,
    LIVE_PREVIEW_H, TRANSPARENT_KEY, COLORS,
    DEFAULT_HOTKEY, MODELS, LANGUAGES, LANGUAGE_LABELS,
)
from util import _resource_path, State

if TYPE_CHECKING:
    from main import App
```

Then paste the entire `class FloatingWindow:` block from `main.py:214-585` verbatim. Change the type annotation in `__init__`:

```python
def __init__(self, app: "App"):
```

(stays as forward ref string — works with `TYPE_CHECKING`).

- [ ] **Step 2: In `main.py`, remove `FloatingWindow` class and add import**

Delete lines 214-585 (whole class). Add:

```python
from ui_capsule import FloatingWindow
```

Remove `import math` from `main.py` if `App` doesn't use it. (Check: `App._wave_tick` uses `math.sin` — keep `import math`.)

- [ ] **Step 3: Verify no missing symbols**

Run: `python -c "import main"`
Expected: No `NameError` / `ImportError`.

- [ ] **Step 4: Smoke test**

Run: `python main.py`
Expected: Window appears, drag works, right-click menu opens, all menu items functional (Model picker, Language picker, Live mode toggle, Tokenize toggle, Set hotkey, Quit).

- [ ] **Step 5: Smoke test interaction**

- Drag capsule to new position → stays.
- Right-click → Set hotkey → enter `ctrl+shift+x` → confirm → press new hotkey → records.
- Toggle Live mode → preview frame appears → record → preview updates.

- [ ] **Step 6: Checkpoint**

Pass → proceed.

---

## Task 8: Final `main.py` cleanup

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Reorder imports cleanly**

Top of `main.py` should be:

```python
"""Thai Voice -> Clipboard. Floating capsule window. Hotkey toggles record."""
# log_setup MUST be first.
from log_setup import log, LOG_PATH  # noqa: F401

import math
import sys
import threading
from collections import deque

import tkinter as tk
from tkinter import messagebox, simpledialog

import numpy as np
import pyperclip

try:
    import keyboard
except ImportError:
    print("keyboard lib missing. pip install keyboard", file=sys.stderr)
    raise

from faster_whisper import WhisperModel

from constants import (
    DEFAULT_HOTKEY, DEFAULT_MODEL, MODELS, DEFAULT_LANGUAGE,
    LANGUAGES, LANGUAGE_LABELS, SAMPLE_RATE, HISTORY_MAX, APP_NAME,
    WAVE_BARS, COLORS, LIVE_TICK_S,
)
from util import State, toast, insert_thai_word_breaks, _get_thai_tokenizer
from audio import AudioRecorder
from transcribe import LiveTranscriber, load_whisper_model
from ui_capsule import FloatingWindow
```

- [ ] **Step 2: Verify final `main.py` line count**

Run: `wc -l main.py`
Expected: ~250 lines (was 1141). Contains only: docstring + imports + `App` class + `_main` + `main` + `if __name__ == "__main__"` block.

- [ ] **Step 3: Verify no dead imports**

For each `import X` and `from X import ...`, confirm at least one usage in the file. Remove unused.

- [ ] **Step 4: Full smoke test (all paths)**

Run `python main.py`. Test in order:

1. Window appears bottom-right, capsule pill shape, mic icon visible.
2. Hotkey `Ctrl+Shift+Space` → wave animates → speak Thai → hotkey again → "Copied" toast → paste from clipboard, verify Thai text with word breaks.
3. Right-click → switch model `tiny` → wait for "Model ready: tiny" toast → record again, verify still works.
4. Right-click → switch language `English` → speak English → verify clipboard.
5. Right-click → enable Live mode → record → preview text updates live → stop → final clipboard.
6. Right-click → toggle Word break OFF → record Thai → clipboard text has NO inter-word spaces.
7. Right-click → Set hotkey → `ctrl+alt+r` → press new hotkey → records.
8. Right-click → Quit → app exits cleanly, no zombie process.

- [ ] **Step 5: Build smoke test (PyInstaller)**

Run: `build.bat`
Expected: `dist\ThaiVoice.exe` produced, no errors. Check `build.bat` output for warnings about missing modules — if `audio`, `transcribe`, etc. are flagged, add them to `hiddenimports` in `ThaiVoice.spec`.

Run: `dist\ThaiVoice.exe`
Expected: Same behavior as `python main.py`. Verify `thai_voice.log` written next to exe.

- [ ] **Step 6: Checkpoint**

All paths pass → proceed.

---

## Task 9: Update docs

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Update `CLAUDE.md` Architecture section**

Replace the `## Architecture` block. New structure:

```markdown
## Architecture

Multi-file layout (split from monolithic `main.py`):

| File | Role |
|---|---|
| `log_setup.py` | Stream guard + logging + excepthook. **MUST be first import** in `main.py`. |
| `constants.py` | All config constants (hotkey, models, colors, dims, timings). |
| `util.py` | `State` enum, `toast`, `_resource_path`, Thai tokenizer, `insert_thai_word_breaks`. |
| `transcribe.py` | `load_whisper_model()` (with CPU/int8 fallback) + `LiveTranscriber` (sliding-window streaming). |
| `audio.py` | `AudioRecorder` — wraps `sd.InputStream`, computes RMS. |
| `ui_capsule.py` | `FloatingWindow` — Tk capsule HUD. |
| `main.py` | `App` state machine + `_main()` + `main()`. |

[Keep the existing "Threading model" + "Critical: PyInstaller --noconsole stream guard" + "Model load fallback chain" + "Build" + "Logging" + "Resource paths" subsections unchanged, but update file path references.]
```

Adjust line references in "stream guard" subsection to point to `log_setup.py` rather than `main.py:11-44`.

- [ ] **Step 2: Update `ROADMAP.md` item 14**

Mark item 14 as done. Add note about new layout matching the suggested split.

- [ ] **Step 3: Delete `main.py.original` backup**

Run: `del main.py.original` (or keep if user prefers — confirm with user first).

- [ ] **Step 4: Final verification**

Run all 8 smoke-test paths from Task 8 step 4 one more time. All pass → done.

---

## Rollback procedure

If any task fails irrecoverably:

```
copy main.py.original main.py
del log_setup.py constants.py util.py audio.py transcribe.py ui_capsule.py
```

`main.py.original` exists from Task 1 step 5.
