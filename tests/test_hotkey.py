"""Test that the keyboard library's parse_hotkey behaves as expected."""

import keyboard
import pytest


def test_parse_valid_hotkey_does_not_raise():
    """Standard hotkey strings parse cleanly."""
    keyboard.parse_hotkey("ctrl+shift+space")
    keyboard.parse_hotkey("ctrl+alt+r")


def test_parse_invalid_hotkey_raises():
    """Garbage hotkey string must raise — App.rebind_hotkey relies on this."""
    with pytest.raises(Exception):  # noqa: B017
        keyboard.parse_hotkey("not a real hotkey @#$%")
