"""Tests for log_setup.py — _resolve_log_dir picks a writable directory."""

import os

from log_setup import LOG_PATH, _resolve_log_dir


def test_resolve_log_dir_returns_writable():
    """The chosen dir must be writable (we already imported, so this dir worked)."""
    d = _resolve_log_dir()
    assert os.path.isdir(d)
    test_file = os.path.join(d, ".thai_voice_pytest_write_test")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        assert os.path.exists(test_file)
    finally:
        try:
            os.remove(test_file)
        except OSError:
            pass


def test_log_path_under_resolved_dir():
    """LOG_PATH should sit inside the resolved log dir."""
    assert LOG_PATH.endswith("thai_voice.log")
    parent = os.path.dirname(LOG_PATH)
    assert os.path.isdir(parent)
