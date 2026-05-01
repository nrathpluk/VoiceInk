"""Thai Voice -> Clipboard. Floating capsule window. Hotkey toggles record."""
import logging
import math
import os
import re
import sys
import threading
import traceback
from collections import deque
from enum import Enum

# ---------- Stream guard (must run BEFORE any 3rd-party import) ----------
# Under PyInstaller --noconsole, sys.stdout/stderr are None. Any library
# (tqdm in faster-whisper, huggingface_hub) writing to them crashes the
# process silently. Redirect to a logfile.
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

import tkinter as tk  # noqa: E402
from tkinter import messagebox, simpledialog  # noqa: E402

# ---------- Logging ----------
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


# ---------- Config ----------
DEFAULT_HOTKEY = "ctrl+shift+space"
DEFAULT_MODEL = "base"
MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_LANGUAGE = "th"
LANGUAGES = ["auto", "th", "en"]   # "auto" = let Whisper detect (+0.5-1s)
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
LIVE_WINDOW_S = 8.0       # transcribe last N seconds
LIVE_TICK_S = 1.5         # rerun every N seconds
LIVE_COMMIT_TAIL_S = 3.0  # keep last N seconds unconfirmed
LIVE_PREVIEW_H = 76       # extra px when live mode on

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


# ---------- Thai tokenizer (lazy) ----------
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
    """Insert spaces between Thai word tokens. Non-Thai segments untouched.

    Whisper Thai output runs words together (no spaces). pythainlp segments
    with newmm engine; we re-join with single space — readable for copy/paste.
    """
    if not text or not _has_thai(text):
        return text
    fn = _get_thai_tokenizer()
    if fn is None:
        return text
    try:
        toks = fn(text, engine="newmm", keep_whitespace=False)
        joined = " ".join(t for t in toks if t)
        # Collapse double spaces (existing whitespace + injected)
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


# ---------- Toast ----------
def toast(title: str, msg: str):
    if not HAS_TOAST:
        return
    try:
        Notification(app_id=APP_NAME, title=title, msg=msg).show()
    except Exception:
        pass


# ---------- Capsule window ----------
class FloatingWindow:
    """Pill-shaped always-on-top mini-HUD."""

    def __init__(self, app: "App"):
        self.app = app
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            log.warning("transparentcolor unsupported on this platform")
        self.root.configure(bg=TRANSPARENT_KEY)

        try:
            ico = _resource_path("icon.ico")
            if os.path.exists(ico):
                self.root.iconbitmap(default=ico)
        except Exception:
            log.exception("iconbitmap failed")

        # Position bottom-right
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - WIN_W - 24
        y = sh - WIN_H - 80
        self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # Visual state
        self._state_key = "idle"
        self._copied_active = False
        self._pending_state_key: str | None = None
        self._pulse_phase = 0.0
        self._wave_phase = 0.0
        self._wave_levels = [0.0] * WAVE_BARS
        self._anim_alive = True
        self._model_loading_text: str | None = None
        self._hotkey_label = DEFAULT_HOTKEY

        # Click / drag
        self._press_x = 0
        self._press_y = 0
        self._click_target = "body"
        self._drag_x = 0
        self._drag_y = 0
        self._drag_started = False

        # Capsule canvas
        self.canvas = tk.Canvas(
            self.root, width=WIN_W, height=WIN_H,
            bg=TRANSPARENT_KEY, highlightthickness=0, bd=0,
        )
        self.canvas.pack(side="top", fill="x")
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._show_menu)

        # Live preview (only shown when live_mode on)
        self.preview_frame = tk.Frame(self.root, bg=TRANSPARENT_KEY)
        self.preview_inner = tk.Frame(
            self.preview_frame, bg=COLORS["preview_bg"],
            highlightthickness=1, highlightbackground="#2a2a40",
        )
        self.preview_inner.pack(padx=8, pady=(0, 6), fill="both", expand=True)
        self.preview_text = tk.Text(
            self.preview_inner, height=4, bg=COLORS["preview_bg"],
            fg=COLORS["fg"], font=("Segoe UI", 8), wrap="word",
            relief="flat", highlightthickness=0,
            insertbackground=COLORS["fg"], padx=6, pady=4,
        )
        self.preview_text.pack(fill="both", expand=True)
        self.preview_text.configure(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.app.quit)

        self._draw_all()
        self.root.after(50, self._animate)

    # ---------- Drawing ----------
    def _rounded_rect(self, x0, y0, x1, y1, r, fill="", outline=""):
        c = self.canvas
        # Two overlapping rectangles + four ovals = filled rounded rect
        items = [
            c.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=outline),
            c.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=outline),
            c.create_oval(x0, y0, x0 + 2 * r, y0 + 2 * r, fill=fill, outline=outline),
            c.create_oval(x1 - 2 * r, y0, x1, y0 + 2 * r, fill=fill, outline=outline),
            c.create_oval(x0, y1 - 2 * r, x0 + 2 * r, y1, fill=fill, outline=outline),
            c.create_oval(x1 - 2 * r, y1 - 2 * r, x1, y1, fill=fill, outline=outline),
        ]
        return items

    def _draw_all(self):
        c = self.canvas
        c.delete("all")

        # Soft glow halo when recording
        if self._state_key == "recording":
            for i, gc in enumerate(("#1f1538", "#241c44", "#291f4e")):
                pad = 3 - i
                self._rounded_rect(
                    -pad, -pad, WIN_W + pad, WIN_H + pad,
                    CAPSULE_RADIUS + pad, fill=gc, outline="",
                )

        # Capsule body
        self._rounded_rect(0, 0, WIN_W, WIN_H, CAPSULE_RADIUS,
                           fill=COLORS["bg"], outline="")

        # Mic button
        if self._state_key == "recording":
            pulse = 1.0 + 0.08 * math.sin(self._pulse_phase)
            r = MIC_R * pulse
            mic_color = COLORS["red"]
            ring = MIC_R * (1.18 + 0.08 * (math.sin(self._pulse_phase) * 0.5 + 0.5))
            c.create_oval(MIC_CX - ring, MIC_CY - ring,
                          MIC_CX + ring, MIC_CY + ring,
                          fill="", outline=COLORS["red"], width=1)
        elif self._state_key == "done":
            r = MIC_R
            mic_color = COLORS["green"]
        else:
            r = MIC_R
            mic_color = COLORS["purple"]

        c.create_oval(MIC_CX - r, MIC_CY - r, MIC_CX + r, MIC_CY + r,
                      fill=mic_color, outline="")

        # Inner glyph
        if self._state_key == "done":
            c.create_line(
                MIC_CX - 9, MIC_CY + 1,
                MIC_CX - 2, MIC_CY + 8,
                MIC_CX + 10, MIC_CY - 7,
                fill="#ffffff", width=3,
                capstyle="round", joinstyle="round",
            )
        else:
            self._draw_mic_glyph(MIC_CX, MIC_CY, "#ffffff")

        # Right side: wave / "Copied!" / model loading text
        right_x = MIC_CX + MIC_R + 18
        right_end = WIN_W - 26
        center_x = (right_x + right_end) // 2
        if self._state_key == "done":
            c.create_text(center_x, MIC_CY, text="Copied!",
                          fill=COLORS["green"],
                          font=("Segoe UI", 13, "bold"), anchor="center")
        elif self._model_loading_text:
            c.create_text(center_x, MIC_CY, text=self._model_loading_text,
                          fill=COLORS["wave_active"],
                          font=("Segoe UI", 9), anchor="center")
        else:
            self._draw_waves(right_x, MIC_CY)

        # Two-dot menu hint
        dot_x = WIN_W - 14
        for off in (-5, 5):
            c.create_oval(dot_x - 2, MIC_CY + off - 2,
                          dot_x + 2, MIC_CY + off + 2,
                          fill=COLORS["menu_dot"], outline="")

    def _draw_mic_glyph(self, cx, cy, color):
        c = self.canvas
        c.create_oval(cx - 6, cy - 12, cx + 6, cy - 1, fill=color, outline="")
        c.create_rectangle(cx - 6, cy - 6, cx + 6, cy + 1, fill=color, outline="")
        c.create_arc(cx - 9, cy - 2, cx + 9, cy + 12, start=200, extent=140,
                     style="arc", outline=color, width=2)
        c.create_line(cx, cy + 11, cx, cy + 16, fill=color, width=2)
        c.create_line(cx - 5, cy + 16, cx + 5, cy + 16, fill=color, width=2)

    def _draw_waves(self, x_start, cy):
        c = self.canvas
        max_h = WIN_H - 24
        idle_heights = [10, 14, 18, 14, 20, 16, 12, 18, 14, 10]
        for i in range(WAVE_BARS):
            x = x_start + i * (WAVE_BAR_W + WAVE_BAR_GAP)
            if self._state_key == "recording":
                lv = self._wave_levels[i]
                h = max(4.0, lv * max_h)
                color = COLORS["wave_active"]
            elif self._state_key == "processing":
                lv = self._wave_levels[i]
                h = max(4.0, lv * max_h)
                color = COLORS["wave_idle"]
            else:
                breathe = 0.85 + 0.15 * math.sin(self._wave_phase * 0.6 + i * 0.7)
                h = idle_heights[i] * breathe
                color = COLORS["wave_idle"]
            y0 = cy - h / 2
            y1 = cy + h / 2
            c.create_rectangle(x, y0, x + WAVE_BAR_W, y1,
                               fill=color, outline="")

    # ---------- Animation tick ----------
    def _animate(self):
        if not self._anim_alive:
            return
        self._pulse_phase += 0.18
        self._wave_phase += 0.12
        # Always redraw to support pulse + wave + idle breathe
        self._draw_all()
        self.root.after(50, self._animate)

    # ---------- Public API ----------
    def render_wave(self, levels: list[float]):
        # Store; redraw happens in _animate
        lv = list(levels) + [0.0] * (WAVE_BARS - len(levels))
        self._wave_levels = lv[:WAVE_BARS]

    def set_state(self, s: State):
        if self._copied_active:
            self._pending_state_key = s.value
            return
        self._state_key = s.value
        self._draw_all()

    def show_copied(self):
        self._copied_active = True
        self._state_key = "done"
        self._draw_all()
        self.root.after(2000, self._clear_copied)

    def _clear_copied(self):
        self._copied_active = False
        nxt = self._pending_state_key or "idle"
        self._pending_state_key = None
        self._state_key = nxt
        self._draw_all()

    def set_hotkey_label(self, hotkey: str):
        self._hotkey_label = hotkey

    def set_model_status(self, text: str, color: str | None = None):
        self._model_loading_text = text or None
        self._draw_all()

    def show_preview(self, on: bool):
        if on:
            if not self.preview_frame.winfo_ismapped():
                self.preview_frame.pack(side="top", fill="x")
            new_h = WIN_H + LIVE_PREVIEW_H
        else:
            if self.preview_frame.winfo_ismapped():
                self.preview_frame.pack_forget()
            new_h = WIN_H
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{WIN_W}x{new_h}+{x}+{y}")

    def set_preview(self, text: str):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.see("end")
        self.preview_text.configure(state="disabled")

    # ---------- Click / drag ----------
    def _inside_capsule(self, x, y):
        r = CAPSULE_RADIUS
        if r <= x <= WIN_W - r:
            return 0 <= y <= WIN_H
        if 0 <= x < r:
            cx, cy = r, WIN_H / 2
            return (x - cx) ** 2 + (y - cy) ** 2 <= cy * cy
        if WIN_W - r < x <= WIN_W:
            cx, cy = WIN_W - r, WIN_H / 2
            return (x - cx) ** 2 + (y - cy) ** 2 <= cy * cy
        return False

    def _hit_test(self, x, y):
        dx = x - MIC_CX
        dy = y - MIC_CY
        if dx * dx + dy * dy <= (MIC_R + 4) ** 2:
            return "mic"
        if x >= WIN_W - 22 and self._inside_capsule(x, y):
            return "menu"
        if self._inside_capsule(x, y):
            return "body"
        return "outside"

    def _on_press(self, e):
        self._press_x = e.x
        self._press_y = e.y
        self._drag_started = False
        self._click_target = self._hit_test(e.x, e.y)
        if self._click_target == "menu":
            self._show_menu(e)
            return
        if self._click_target in ("body", "mic"):
            self._drag_x = e.x_root - self.root.winfo_x()
            self._drag_y = e.y_root - self.root.winfo_y()

    def _on_drag(self, e):
        if self._click_target not in ("body", "mic"):
            return
        if (not self._drag_started
                and abs(e.x - self._press_x) + abs(e.y - self._press_y) < 5):
            return
        self._drag_started = True
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, e):
        if self._click_target == "mic" and not self._drag_started:
            self.app.toggle()

    # ---------- Right-click menu ----------
    def _show_menu(self, e):
        menu = tk.Menu(self.root, tearoff=0,
                       bg=COLORS["bg"], fg=COLORS["fg"],
                       activebackground=COLORS["purple"],
                       activeforeground="#ffffff", borderwidth=0)

        model_menu = tk.Menu(menu, tearoff=0,
                             bg=COLORS["bg"], fg=COLORS["fg"],
                             activebackground=COLORS["purple"],
                             activeforeground="#ffffff")
        for m in MODELS:
            mark = "● " if m == self.app.model_name else "   "
            model_menu.add_command(
                label=f"{mark}{m}",
                command=lambda name=m: self.app.change_model(name),
            )
        menu.add_cascade(label="Model", menu=model_menu)

        lang_menu = tk.Menu(menu, tearoff=0,
                            bg=COLORS["bg"], fg=COLORS["fg"],
                            activebackground=COLORS["purple"],
                            activeforeground="#ffffff")
        for lc in LANGUAGES:
            mark = "● " if lc == self.app.language else "   "
            lang_menu.add_command(
                label=f"{mark}{LANGUAGE_LABELS[lc]}",
                command=lambda c=lc: self.app.change_language(c),
            )
        menu.add_cascade(label="Language", menu=lang_menu)

        hist_menu = tk.Menu(menu, tearoff=0,
                            bg=COLORS["bg"], fg=COLORS["fg"],
                            activebackground=COLORS["purple"],
                            activeforeground="#ffffff")
        if self.app.history:
            for h in self.app.history:
                lbl = h if len(h) <= 40 else h[:37] + "..."
                hist_menu.add_command(
                    label=lbl, command=lambda t=h: pyperclip.copy(t))
        else:
            hist_menu.add_command(label="(empty)", state="disabled")
        menu.add_cascade(label="History", menu=hist_menu)

        menu.add_separator()
        live_mark = "● " if self.app.live_mode else "   "
        menu.add_command(label=f"{live_mark}Live mode (streaming)",
                         command=self.app.toggle_live_mode)
        tok_mark = "● " if self.app.tokenize_thai else "   "
        menu.add_command(label=f"{tok_mark}ตัดคำไทย (Thai word break)",
                         command=self.app.toggle_tokenize)
        menu.add_command(label=f"Hotkey: {self._hotkey_label}",
                         command=self.app.prompt_hotkey)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.app.quit)

        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()


# ---------- Live streaming ----------
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
        self.language = language        # None or "auto" -> Whisper detects
        self.committed = ""
        self.tentative = ""
        self.committed_samples = 0      # samples already finalized
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
        # Cap window
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
                beam_size=1,        # streaming = speed > beam quality
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


# ---------- App ----------
class App:
    def __init__(self):
        self.model_name = DEFAULT_MODEL
        self.hotkey = DEFAULT_HOTKEY
        self.language = DEFAULT_LANGUAGE        # "auto" | "th" | "en"
        self.tokenize_thai = True               # add spaces between Thai words
        self.state = State.IDLE
        self.lock = threading.Lock()
        self.history: deque = deque(maxlen=HISTORY_MAX)
        self.recording_frames: list = []
        self.stream = None
        self.model: WhisperModel | None = None
        self.win: FloatingWindow | None = None
        self.model_ready = threading.Event()
        self.model_error: Exception | None = None
        self._loader_thread: threading.Thread | None = None
        # Audio level (RMS 0..1, written from audio cb, read from UI tick)
        self.current_rms = 0.0
        self._wave_smooth = [0.0] * WAVE_BARS
        self._wave_phase = 0.0
        # Live streaming
        self.live_mode = False
        self.live: LiveTranscriber | None = None
        self._live_thread: threading.Thread | None = None
        self._live_stop = threading.Event()

    # --- Threadsafe UI helper ---
    def ui(self, fn, *args, **kwargs):
        if self.win is not None:
            try:
                self.win.root.after(0, lambda: fn(*args, **kwargs))
            except Exception:
                pass

    # --- Model ---
    def load_model_async(self):
        """Kick off background model load. Never blocks UI thread."""
        if self._loader_thread is not None and self._loader_thread.is_alive():
            log.info("model loader already running, skip")
            return
        self.model = None
        self.model_error = None
        self.model_ready.clear()
        self.ui(lambda: self.win.set_model_status(
            f"กำลังโหลด model '{self.model_name}'...", COLORS["wave_active"]))
        t = threading.Thread(target=self._load_model_worker,
                             name="model-loader", daemon=True)
        self._loader_thread = t
        t.start()

    def _load_model_worker(self):
        name = self.model_name
        log.info("Loading model %r (device=auto)", name)
        toast(APP_NAME, f"Loading model '{name}'...")
        loaded: WhisperModel | None = None
        err: Exception | None = None
        try:
            loaded = WhisperModel(name, device="auto", compute_type="auto")
            log.info("Model loaded: device=auto compute=auto")
        except Exception as e:
            log.warning("auto load failed: %s — retry CPU/int8", e)
            try:
                loaded = WhisperModel(name, device="cpu", compute_type="int8")
                log.info("Model loaded: device=cpu compute=int8")
            except Exception as e2:
                log.exception("Model load failed (cpu fallback also failed)")
                err = e2
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

    def _on_model_loaded(self):
        if self.win is not None:
            self.win.set_model_status("")
        toast(APP_NAME, f"Model ready: {self.model_name}")

    def _on_model_load_failed(self, err: Exception | None):
        msg = str(err) if err else "unknown error"
        if self.win is not None:
            self.win.set_model_status("model load failed", COLORS["red"])
        toast("Model load failed", msg[:100])
        try:
            messagebox.showerror(
                "ThaiVoice — โหลด model ไม่สำเร็จ",
                f"โหลด model '{self.model_name}' ไม่สำเร็จ\n\n"
                f"{msg}\n\n"
                "ตรวจสอบ:\n"
                " • การเชื่อมต่ออินเทอร์เน็ต (ครั้งแรกต้องดาวน์โหลด)\n"
                " • พื้นที่ดิสก์ว่างเพียงพอ\n"
                " • สิทธิ์เขียนไฟล์ใน cache folder\n\n"
                f"รายละเอียดใน log:\n{LOG_PATH}",
                parent=self.win.root if self.win else None,
            )
        except Exception:
            log.exception("messagebox error")

    def get_model(self) -> WhisperModel:
        """Wait for background loader. Raise if load failed."""
        if self.model is not None:
            return self.model
        if not self.model_ready.is_set():
            log.info("waiting for background model load...")
            self.model_ready.wait()
        if self.model is None:
            raise RuntimeError(
                f"model not loaded: {self.model_error}"
                if self.model_error else "model not loaded")
        return self.model

    def toggle_live_mode(self):
        if self.state != State.IDLE:
            toast(APP_NAME, "Stop recording first")
            return
        self.live_mode = not self.live_mode
        toast(APP_NAME, f"Live mode: {'ON' if self.live_mode else 'OFF'}")
        if self.win is not None:
            self.win.show_preview(self.live_mode)
            if not self.live_mode:
                self.win.set_preview("")

    def change_model(self, name: str):
        if name == self.model_name:
            return
        self.model_name = name
        toast(APP_NAME, f"Model: {name}")
        self.load_model_async()

    def change_language(self, lang: str):
        if lang not in LANGUAGES or lang == self.language:
            return
        self.language = lang
        if self.live is not None:
            self.live.language = lang
        toast(APP_NAME, f"Language: {LANGUAGE_LABELS.get(lang, lang)}")

    def toggle_tokenize(self):
        self.tokenize_thai = not self.tokenize_thai
        toast(APP_NAME,
              f"Thai word break: {'ON' if self.tokenize_thai else 'OFF'}")
        # Warm tokenizer in background so first toggle->commit isn't laggy
        if self.tokenize_thai:
            threading.Thread(target=_get_thai_tokenizer,
                             name="pythainlp-warmup", daemon=True).start()

    # --- Recording ---
    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        self.recording_frames.append(indata.copy())
        if self.live is not None:
            self.live.feed(indata.flatten().astype(np.float32))
        # RMS for waveform UI (atomic float write — fine across threads)
        try:
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            self.current_rms = rms
        except Exception:
            pass

    def start_record(self):
        self.recording_frames = []
        try:
            sd.query_devices(kind="input")
        except Exception as e:
            toast("No mic", str(e)[:100])
            raise
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop_record(self) -> np.ndarray:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.current_rms = 0.0
        if not self.recording_frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self.recording_frames, axis=0).flatten().astype(np.float32)

    # --- Pipeline ---
    def toggle(self):
        log.debug("toggle called, state=%s", self.state.value)
        with self.lock:
            if self.state == State.IDLE:
                # Init live streamer BEFORE starting stream so callback finds it
                if self.live_mode:
                    if self.model is None:
                        toast(APP_NAME, "Model not ready yet")
                        return
                    self.live = LiveTranscriber(self.model, SAMPLE_RATE,
                                                language=self.language)
                    self._live_stop.clear()
                    self._live_thread = threading.Thread(
                        target=self._live_worker, name="live-stream", daemon=True)
                try:
                    self.start_record()
                except Exception:
                    log.exception("start_record failed")
                    self.live = None
                    return
                self.set_state(State.RECORDING)
                if self._live_thread is not None:
                    self._live_thread.start()
                log.info("recording started (live=%s)", self.live_mode)
            elif self.state == State.RECORDING:
                try:
                    audio = self.stop_record()
                    log.info("recording stopped, samples=%d", audio.size)
                except Exception as e:
                    log.exception("stop_record failed")
                    toast("Record error", str(e)[:100])
                    self.set_state(State.IDLE)
                    return
                if self.live is not None:
                    self._live_stop.set()
                    self.set_state(State.PROCESSING)
                    threading.Thread(target=self._finalize_live,
                                     name="live-finalize", daemon=True).start()
                else:
                    self.set_state(State.PROCESSING)
                    threading.Thread(target=self._process, args=(audio,),
                                     name="process", daemon=True).start()

    def _process(self, audio: np.ndarray):
        try:
            log.info("process: samples=%d (%.2fs)",
                     audio.size, audio.size / SAMPLE_RATE)
            if audio.size < SAMPLE_RATE * 0.3:
                log.info("audio too short, abort")
                toast(APP_NAME, "Recording too short")
                return
            model = self.get_model()
            lang = None if self.language in (None, "auto") else self.language
            log.info("transcribe start (lang=%s beam=5 vad=on)", lang or "auto")
            segments, _info = model.transcribe(
                audio,
                language=lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            text = "".join(seg.text for seg in segments).strip()
            if self.tokenize_thai:
                text = insert_thai_word_breaks(text)
            log.info("transcribe done, text_len=%d", len(text))
            if not text:
                toast(APP_NAME, "No speech detected")
                return
            pyperclip.copy(text)
            self.history.appendleft(text)
            preview = text if len(text) <= 60 else text[:57] + "..."
            toast("Copied", preview)
            self.ui(self._win_show_copied)
        except Exception as e:
            log.exception("process failed")
            toast("Transcribe error", str(e)[:100])
        finally:
            self.set_state(State.IDLE)

    # --- Live streaming workers ---
    def _live_worker(self):
        log.info("live worker start")
        while not self._live_stop.wait(LIVE_TICK_S):
            if self.live is None:
                break
            try:
                self.live.tick(final=False)
                text = self.live.full_text()
                self.ui(self._apply_live_preview, text)
                if self.live.committed:
                    out = self.live.committed
                    if self.tokenize_thai:
                        out = insert_thai_word_breaks(out)
                    pyperclip.copy(out)
            except Exception:
                log.exception("live tick failed")
        log.info("live worker exit")

    def _finalize_live(self):
        try:
            if self.live is not None:
                self.live.tick(final=True)
                text = self.live.full_text()
                if text and self.tokenize_thai:
                    text = insert_thai_word_breaks(text)
                if text:
                    pyperclip.copy(text)
                    self.history.appendleft(text)
                    preview = text if len(text) <= 60 else text[:57] + "..."
                    toast("Copied", preview)
                    self.ui(self._win_show_copied)
                else:
                    toast(APP_NAME, "No speech detected")
                self.ui(self._apply_live_preview, text)
        except Exception:
            log.exception("finalize_live failed")
            toast("Transcribe error", "see log")
        finally:
            self.live = None
            self._live_thread = None
            self.set_state(State.IDLE)

    def _apply_live_preview(self, text: str):
        if self.win is not None:
            self.win.set_preview(text)

    # --- UI ---
    def set_state(self, s: State):
        self.state = s
        self.ui(self._apply_state, s)

    def _apply_state(self, s: State):
        if self.win is not None:
            self.win.set_state(s)

    def _win_show_copied(self):
        if self.win is not None:
            self.win.show_copied()

    # --- Waveform animation tick (UI thread, ~30fps) ---
    def _wave_tick(self):
        if self.win is None:
            return
        self._wave_phase += 0.18
        targets = [0.0] * WAVE_BARS

        if self.state == State.RECORDING:
            # RMS -> normalized 0..1, log-ish scale (typical speech ~0.02..0.3)
            rms = self.current_rms
            level = min(1.0, max(0.0, (rms * 8.0) ** 0.7))
            # Per-bar variation: bell shape across N bars + phase wobble
            for i in range(WAVE_BARS):
                t = i / max(1, WAVE_BARS - 1)
                shape = 0.45 + 0.55 * math.sin(t * math.pi)
                wob = 0.80 + 0.20 * math.sin(self._wave_phase + i * 0.9)
                targets[i] = max(0.04, level * shape * wob)
        elif self.state == State.PROCESSING:
            # Slow decay toward baseline
            for i in range(WAVE_BARS):
                targets[i] = self._wave_smooth[i] * 0.85
        else:  # IDLE
            for i in range(WAVE_BARS):
                targets[i] = 0.06 + 0.03 * (
                    0.5 + 0.5 * math.sin(self._wave_phase * 0.3 + i * 1.1))

        # Smooth toward target (asymmetric: fast attack, slow release)
        for i in range(WAVE_BARS):
            cur = self._wave_smooth[i]
            tgt = targets[i]
            alpha = 0.55 if tgt > cur else 0.25
            self._wave_smooth[i] = cur + (tgt - cur) * alpha

        try:
            self.win.render_wave(self._wave_smooth)
        except Exception:
            pass
        self.win.root.after(33, self._wave_tick)

    # --- Hotkey ---
    def rebind_hotkey(self, new_hotkey: str):
        try:
            keyboard.parse_hotkey(new_hotkey)
        except Exception as e:
            toast("Invalid hotkey", str(e)[:100])
            return False
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.hotkey = new_hotkey
        keyboard.add_hotkey(new_hotkey, self.toggle)
        toast(APP_NAME, f"Hotkey: {new_hotkey}")
        self.ui(lambda: self.win.set_hotkey_label(new_hotkey))
        return True

    def prompt_hotkey(self):
        # Run on Tk main thread (already is, since called from menu)
        try:
            val = simpledialog.askstring(
                "Set hotkey",
                "Enter hotkey (e.g. ctrl+shift+space):",
                initialvalue=self.hotkey,
                parent=self.win.root,
            )
            if val:
                self.rebind_hotkey(val.strip())
        except Exception as e:
            toast("Hotkey dialog error", str(e)[:100])

    # --- Quit ---
    def quit(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        if self.win is not None:
            try:
                self.win.root.destroy()
            except Exception:
                pass


def _main():
    log.info("python=%s exe_frozen=%s", sys.version.split()[0],
             getattr(sys, "frozen", False))
    app = App()
    app.win = FloatingWindow(app)
    app.win.set_hotkey_label(app.hotkey)

    try:
        keyboard.add_hotkey(app.hotkey, app.toggle)
        log.info("hotkey bound: %s", app.hotkey)
    except Exception:
        log.exception("hotkey bind failed")
        toast("Hotkey error", "Run as admin if needed")

    # UI is up — now start model load in the background. Never block UI.
    app.win.root.after(50, app.load_model_async)
    app.win.root.after(100, app._wave_tick)

    try:
        app.win.root.mainloop()
    except Exception:
        log.exception("mainloop crashed")
        raise
    log.info("=== ThaiVoice exit ===")


def main():
    try:
        _main()
    except SystemExit:
        raise
    except Exception:
        log.exception("FATAL uncaught in main")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "ThaiVoice — Fatal error",
                f"แอปเกิด error ที่จัดการไม่ได้และต้องปิด\n\n"
                f"รายละเอียดใน log:\n{LOG_PATH}",
                parent=root,
            )
            root.destroy()
        except Exception:
            log.exception("messagebox failed during fatal handler")
        sys.exit(1)


if __name__ == "__main__":
    main()
