"""Log + stream guard. MUST be first import in src/app/main.py.

Under PyInstaller --noconsole, sys.stdout/sys.stderr are None. Any 3rd-party
write (tqdm in faster-whisper, hf_hub) crashes silently. Redirect early.
"""

import logging
import os
import sys
import threading
import traceback


def _resolve_log_dir():
    if getattr(sys, "frozen", False):
        primary = os.path.dirname(sys.executable)
    else:
        # Dev: project root = three parents up from src/app/utils/log_setup.py
        primary = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
        )
    for candidate in (
        primary,
        os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ThaiVoice"),
        os.path.expanduser("~"),
    ):
        try:
            os.makedirs(candidate, exist_ok=True)
            test = os.path.join(candidate, ".thai_voice_write_test")
            with open(test, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(test)
            return candidate
        except Exception:
            continue
    return os.getcwd()


_LOG_DIR = _resolve_log_dir()
LOG_PATH = os.path.join(_LOG_DIR, "thai_voice.log")
_STREAM_PATH = os.path.join(_LOG_DIR, "thai_voice.stream.log")

if sys.stdout is None or getattr(sys.stdout, "fileno", None) is None:
    # Intentional long-lived file: replaces sys.stdout under PyInstaller --noconsole.
    sys.stdout = open(_STREAM_PATH, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
if sys.stderr is None or getattr(sys.stderr, "fileno", None) is None:
    sys.stderr = sys.stdout

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("thaivoice")


def _excepthook(exc_type, exc_value, exc_tb):
    log.error("UNCAUGHT: %s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


sys.excepthook = _excepthook
try:
    threading.excepthook = lambda args: log.error(
        "THREAD UNCAUGHT in %s: %s",
        args.thread.name,
        "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
    )
except Exception:
    pass

log.info("=== ThaiVoice start. log=%s ===", LOG_PATH)
