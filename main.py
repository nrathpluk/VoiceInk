"""Thai Voice -> Clipboard. Floating capsule window. Hotkey toggles record."""

# ruff: noqa: I001
# Import sorting disabled file-wide: log_setup MUST be first non-docstring import
# (installs stream guard + logging before any 3rd-party import). Reordering would
# break --noconsole builds. See CLAUDE.md "Critical: PyInstaller stream guard".
from log_setup import log, LOG_PATH  # noqa: F401

# stdlib
import math
import sys
import threading
from collections import deque

# Tk (stdlib but heavy — group separately)
import tkinter as tk
from tkinter import messagebox, simpledialog

# 3rd-party
import numpy as np
import pyperclip

try:
    import keyboard
except ImportError:
    print("keyboard lib missing. pip install keyboard", file=sys.stderr)
    raise

from faster_whisper import WhisperModel

# local modules
from constants import (
    DEFAULT_HOTKEY,
    DEFAULT_MODEL,
    MODELS,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    LANGUAGE_LABELS,
    SAMPLE_RATE,
    HISTORY_MAX,
    APP_NAME,
    WAVE_BARS,
    LIVE_TICK_S,
    COLORS,
)
from util import State, toast, insert_thai_word_breaks, _get_thai_tokenizer
from config import _read_config, _write_config
from audio import AudioRecorder
from transcribe import LiveTranscriber, load_whisper_model
from ui_capsule import FloatingWindow


# ---------- App ----------
class App:
    def __init__(self):
        cfg = _read_config()
        self._cfg = cfg
        m = cfg.get("model", DEFAULT_MODEL)
        self.model_name = m if m in MODELS else DEFAULT_MODEL
        self.hotkey = cfg.get("hotkey", DEFAULT_HOTKEY) or DEFAULT_HOTKEY
        lg = cfg.get("language", DEFAULT_LANGUAGE)
        self.language = lg if lg in LANGUAGES else DEFAULT_LANGUAGE
        self.tokenize_thai = bool(cfg.get("tokenize_thai", True))
        self.state = State.IDLE
        self.lock = threading.Lock()
        self.history: deque = deque(maxlen=HISTORY_MAX)
        self.audio = AudioRecorder()
        self.model: WhisperModel | None = None
        self.win: FloatingWindow | None = None
        self.model_ready = threading.Event()
        self.model_error: Exception | None = None
        self._loader_thread: threading.Thread | None = None
        self._wave_smooth = [0.0] * WAVE_BARS
        self._wave_phase = 0.0
        # Live streaming
        self.live_mode = bool(cfg.get("live_mode", False))
        self.live: LiveTranscriber | None = None
        self._live_thread: threading.Thread | None = None
        self._live_stop = threading.Event()
        self.auto_update = bool(cfg.get("auto_update", True))

    # --- Settings ---
    def _save_settings(self):
        cfg = dict(self._cfg) if isinstance(self._cfg, dict) else {}
        cfg.update(
            hotkey=self.hotkey,
            model=self.model_name,
            language=self.language,
            tokenize_thai=self.tokenize_thai,
            live_mode=self.live_mode,
            auto_update=self.auto_update,
        )
        if self.win is not None:
            try:
                cfg["window_x"] = int(self.win.root.winfo_x())
                cfg["window_y"] = int(self.win.root.winfo_y())
            except Exception:
                pass
        self._cfg = cfg
        _write_config(cfg)

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
        self.ui(
            lambda: self.win.set_model_status(
                f"กำลังโหลด model '{self.model_name}'...", COLORS["wave_active"]
            )
        )
        t = threading.Thread(target=self._load_model_worker, name="model-loader", daemon=True)
        self._loader_thread = t
        t.start()

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
                f"model not loaded: {self.model_error}" if self.model_error else "model not loaded"
            )
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
        self._save_settings()

    def change_model(self, name: str):
        if name == self.model_name:
            return
        self.model_name = name
        toast(APP_NAME, f"Model: {name}")
        self.load_model_async()
        self._save_settings()

    def change_language(self, lang: str):
        if lang not in LANGUAGES or lang == self.language:
            return
        self.language = lang
        if self.live is not None:
            self.live.language = lang
        toast(APP_NAME, f"Language: {LANGUAGE_LABELS.get(lang, lang)}")
        self._save_settings()

    def toggle_tokenize(self):
        self.tokenize_thai = not self.tokenize_thai
        toast(APP_NAME, f"Thai word break: {'ON' if self.tokenize_thai else 'OFF'}")
        # Warm tokenizer in background so first toggle->commit isn't laggy
        if self.tokenize_thai:
            threading.Thread(
                target=_get_thai_tokenizer, name="pythainlp-warmup", daemon=True
            ).start()
        self._save_settings()

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
                    self.live = LiveTranscriber(self.model, SAMPLE_RATE, language=self.language)
                    self._live_stop.clear()
                    self._live_thread = threading.Thread(
                        target=self._live_worker, name="live-stream", daemon=True
                    )

                def _on_audio_chunk(chunk):
                    if self.live is not None:
                        self.live.feed(chunk)

                try:
                    self.audio.start(on_frames=_on_audio_chunk)
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
                    audio = self.audio.stop()
                    log.info("recording stopped, samples=%d", audio.size)
                except Exception as e:
                    log.exception("stop_record failed")
                    toast("Record error", str(e)[:100])
                    self.set_state(State.IDLE)
                    return
                if self.live is not None:
                    self._live_stop.set()
                    self.set_state(State.PROCESSING)
                    threading.Thread(
                        target=self._finalize_live, name="live-finalize", daemon=True
                    ).start()
                else:
                    self.set_state(State.PROCESSING)
                    threading.Thread(
                        target=self._process, args=(audio,), name="process", daemon=True
                    ).start()

    def _process(self, audio: np.ndarray):
        try:
            log.info("process: samples=%d (%.2fs)", audio.size, audio.size / SAMPLE_RATE)
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
                vad_parameters={"min_silence_duration_ms": 500},
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
            rms = self.audio.current_rms
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
                targets[i] = 0.06 + 0.03 * (0.5 + 0.5 * math.sin(self._wave_phase * 0.3 + i * 1.1))

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
        self._save_settings()
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
            self._save_settings()
        except Exception:
            log.exception("save settings on quit failed")
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.audio.force_close()
        if self.win is not None:
            try:
                self.win.root.destroy()
            except Exception:
                pass


def _update_check_worker(app: "App"):
    """Background: check GitHub for newer release. Toast if found."""
    try:
        from updater import check_for_update

        new_tag = check_for_update()
    except Exception:
        log.exception("update-check thread crashed")
        return
    if new_tag:
        app.ui(
            lambda: toast(
                "ThaiVoice update available",
                f"New version {new_tag} is available on GitHub",
            )
        )


def _main():
    log.info("python=%s exe_frozen=%s", sys.version.split()[0], getattr(sys, "frozen", False))
    app = App()
    app.win = FloatingWindow(app)
    app.win.set_hotkey_label(app.hotkey)
    if app.live_mode:
        app.win.show_preview(True)

    try:
        keyboard.add_hotkey(app.hotkey, app.toggle)
        log.info("hotkey bound: %s", app.hotkey)
    except Exception:
        log.exception("hotkey bind failed")
        toast("Hotkey error", "Run as admin if needed")

    # UI is up — now start model load in the background. Never block UI.
    app.win.root.after(50, app.load_model_async)
    app.win.root.after(100, app._wave_tick)

    if app.auto_update:
        threading.Thread(
            target=_update_check_worker, args=(app,), name="update-check", daemon=True
        ).start()

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
                f"แอปเกิด error ที่จัดการไม่ได้และต้องปิด\n\nรายละเอียดใน log:\n{LOG_PATH}",
                parent=root,
            )
            root.destroy()
        except Exception:
            log.exception("messagebox failed during fatal handler")
        sys.exit(1)


if __name__ == "__main__":
    main()
