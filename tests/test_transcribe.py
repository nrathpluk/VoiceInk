"""Tests for transcribe.py — LiveTranscriber + load_whisper_model fallback."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

import transcribe
from transcribe import LiveTranscriber


class _FakeSegment:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


class _FakeModel:
    """Fake WhisperModel that returns canned segments based on audio length."""

    def __init__(self, segments_to_return):
        self._segs = segments_to_return
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio.size, kwargs))
        return iter(self._segs), SimpleNamespace()


def test_live_feed_then_full_text_empty_when_short():
    """Less than 0.6s of audio: tick() returns without transcribing."""
    model = _FakeModel([])
    lt = LiveTranscriber(model, sample_rate=16000, language="th")
    # 0.3s of silence
    lt.feed(np.zeros(int(16000 * 0.3), dtype=np.float32))
    lt.tick(final=False)
    assert lt.committed == ""
    assert lt.tentative == ""
    assert model.calls == []  # nothing transcribed


def test_live_final_commits_all_segments():
    """final=True commits everything, even short tail."""
    segs = [_FakeSegment("hello", 0.0, 1.0), _FakeSegment("world", 1.0, 2.0)]
    model = _FakeModel(segs)
    lt = LiveTranscriber(model, sample_rate=16000, language="en")
    # 2 seconds of dummy float32 audio
    lt.feed(np.ones(16000 * 2, dtype=np.float32))
    lt.tick(final=True)
    assert "hello" in lt.committed
    assert "world" in lt.committed
    assert lt.tentative == ""
    # committed_samples advanced
    assert lt.committed_samples > 0


def test_live_full_text_combines_committed_and_tentative():
    lt = LiveTranscriber(_FakeModel([]), sample_rate=16000)
    lt.committed = "alpha"
    lt.tentative = "beta"
    assert lt.full_text() == "alpha beta"
    lt.tentative = ""
    assert lt.full_text() == "alpha"


def test_load_whisper_model_uses_auto_first():
    """load_whisper_model tries device='auto' first."""
    with patch.object(transcribe, "WhisperModel") as Wm:
        instance = MagicMock()
        Wm.return_value = instance
        out = transcribe.load_whisper_model("base")
        Wm.assert_called_once_with("base", device="auto", compute_type="auto")
        assert out is instance


def test_load_whisper_model_falls_back_to_cpu_int8():
    """If 'auto' raises, fallback to cpu/int8."""
    with patch.object(transcribe, "WhisperModel") as Wm:
        cpu_instance = MagicMock()
        Wm.side_effect = [RuntimeError("no cuda"), cpu_instance]
        out = transcribe.load_whisper_model("base")
        assert Wm.call_count == 2
        # 2nd call has cpu/int8
        _, kwargs = Wm.call_args_list[1]
        assert kwargs == {"device": "cpu", "compute_type": "int8"}
        assert out is cpu_instance


def test_load_whisper_model_raises_when_both_fail():
    """If both auto and cpu fail, the cpu exception propagates."""
    with patch.object(transcribe, "WhisperModel") as Wm:
        Wm.side_effect = [RuntimeError("no cuda"), ValueError("model not found")]
        try:
            transcribe.load_whisper_model("base")
        except ValueError as e:
            assert "model not found" in str(e)
        else:
            raise AssertionError("expected ValueError to propagate")
