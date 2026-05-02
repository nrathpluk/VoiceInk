"""WhisperModel loader + sliding-window streaming transcriber."""

import threading

import numpy as np
from faster_whisper import WhisperModel

from constants import LIVE_COMMIT_TAIL_S, LIVE_WINDOW_S, SAMPLE_RATE
from log_setup import log


def load_whisper_model(name: str) -> WhisperModel:
    """Load WhisperModel with auto -> cpu/int8 fallback. Raises on total failure.

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

    def __init__(
        self, model: WhisperModel, sample_rate: int = SAMPLE_RATE, language: str | None = "th"
    ):
        self.model = model
        self.sr = sample_rate
        self.language = language  # None or "auto" -> Whisper detects
        self.committed = ""
        self.tentative = ""
        self.committed_samples = 0  # samples already finalized
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
        return full[self.committed_samples :]

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
                beam_size=1,  # streaming = speed > beam quality
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
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
