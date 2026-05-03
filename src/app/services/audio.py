"""Mic recording wrapper around sounddevice.

AudioRecorder owns the sd.InputStream. Caller supplies an optional
on_frames callback for live streaming. stop() returns the concatenated
float32 buffer.
"""

from collections.abc import Callable

import numpy as np
import sounddevice as sd

from app.core.constants import SAMPLE_RATE
from app.utils.log_setup import log


class AudioRecorder:
    def __init__(self):
        self.stream: sd.InputStream | None = None
        self.frames: list[np.ndarray] = []
        self.current_rms: float = 0.0
        self._on_frames: Callable[[np.ndarray], None] | None = None

    def start(self, on_frames: Callable[[np.ndarray], None] | None = None):
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
        """Stop stream + return concatenated buffer."""
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
