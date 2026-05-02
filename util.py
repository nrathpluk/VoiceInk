"""Small helpers: Thai tokenizer, resource path, State enum, toast notifications."""

import os
import re
import sys
from enum import Enum

from constants import APP_NAME
from log_setup import log

try:
    from winotify import Notification

    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False


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


def toast(title: str, msg: str):
    if not HAS_TOAST:
        return
    try:
        Notification(app_id=APP_NAME, title=title, msg=msg).show()
    except Exception:
        pass
