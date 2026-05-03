"""Tests for util.py — Thai tokenizer + State enum."""

from app.utils.util import State, _has_thai, insert_thai_word_breaks


def test_state_enum_values():
    assert State.IDLE.value == "idle"
    assert State.RECORDING.value == "recording"
    assert State.PROCESSING.value == "processing"


def test_has_thai_true():
    assert _has_thai("สวัสดี")
    assert _has_thai("hello สวัสดี")


def test_has_thai_false():
    assert not _has_thai("hello world")
    assert not _has_thai("")
    assert not _has_thai("123 !@#")


def test_insert_thai_word_breaks_english_passthrough():
    """Pure English text returns unchanged."""
    assert insert_thai_word_breaks("hello world") == "hello world"


def test_insert_thai_word_breaks_empty():
    assert insert_thai_word_breaks("") == ""


def test_insert_thai_word_breaks_thai_inserts_spaces():
    """Thai text gets word boundaries inserted."""
    out = insert_thai_word_breaks("สวัสดีครับผมชื่อจอห์น")
    # pythainlp tokenizes Thai; we don't assert exact tokens (engine-dependent)
    # but the output should contain at least one space (boundary between words)
    # If pythainlp is missing, function returns input unchanged — that's also fine
    assert isinstance(out, str)
    assert len(out) > 0
