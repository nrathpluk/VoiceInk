"""Tests for updater.py — version compare logic only (no network)."""

from updater import _normalize, is_newer


def test_normalize_v_prefix():
    assert _normalize("v1.2.3") == (1, 2, 3)
    assert _normalize("V0.1.0") == (0, 1, 0)


def test_normalize_no_prefix():
    assert _normalize("2.0.0") == (2, 0, 0)


def test_normalize_partial():
    assert _normalize("1") == (1,)
    assert _normalize("1.2") == (1, 2)


def test_normalize_with_suffix():
    """v1.2.3-rc1 -> (1, 2, 3) for the digit parts."""
    assert _normalize("1.2.3-rc1") == (1, 2, 3)


def test_is_newer_true():
    assert is_newer("v0.2.0", local="0.1.0")
    assert is_newer("1.0.0", local="0.9.99")


def test_is_newer_false_equal():
    assert not is_newer("v0.1.0", local="0.1.0")


def test_is_newer_false_older():
    assert not is_newer("v0.0.9", local="0.1.0")


def test_is_newer_handles_bad_input():
    """Garbage input — must not raise."""
    assert is_newer("not-a-version", local="0.1.0") is False
    assert is_newer("", local="0.1.0") is False
