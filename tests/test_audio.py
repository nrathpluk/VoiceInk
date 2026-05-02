"""Tests for audio.py — AudioRecorder buffer behavior with sd mocked."""

from unittest.mock import MagicMock, patch

import numpy as np

import audio


def test_stop_with_no_frames_returns_empty_array():
    rec = audio.AudioRecorder()
    out = rec.stop()
    assert isinstance(out, np.ndarray)
    assert out.size == 0
    assert out.dtype == np.float32


def test_force_close_handles_no_stream():
    """force_close on never-started recorder — no error."""
    rec = audio.AudioRecorder()
    rec.force_close()  # must not raise
    assert rec.stream is None


def test_cb_appends_frames_and_computes_rms():
    """Simulate sd callback directly with a known-amplitude signal."""
    rec = audio.AudioRecorder()
    # Pretend stream is started; we only test the callback path.
    sig = np.full((480, 1), 0.5, dtype=np.float32)  # 30ms @ 16kHz, 1 channel
    rec._cb(sig, frames=480, time_info=None, status=None)
    assert len(rec.frames) == 1
    assert rec.frames[0].shape == (480, 1)
    # RMS of constant 0.5 is 0.5
    assert abs(rec.current_rms - 0.5) < 1e-5


def test_on_frames_callback_invoked():
    received = []

    def cb(chunk):
        received.append(chunk.copy())

    rec = audio.AudioRecorder()
    rec._on_frames = cb  # bypass sd
    sig = np.full((100, 1), 0.1, dtype=np.float32)
    rec._cb(sig, frames=100, time_info=None, status=None)
    assert len(received) == 1
    assert received[0].shape == (100,)  # flattened
    assert received[0].dtype == np.float32


def test_start_calls_sd_inputstream():
    """AudioRecorder.start opens an InputStream and starts it."""
    with (
        patch.object(audio.sd, "query_devices") as qd,
        patch.object(audio.sd, "InputStream") as InputStream,
    ):
        stream_mock = MagicMock()
        InputStream.return_value = stream_mock
        rec = audio.AudioRecorder()
        rec.start()
        qd.assert_called_once_with(kind="input")
        InputStream.assert_called_once()
        stream_mock.start.assert_called_once()
