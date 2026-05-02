"""App-wide constants. No imports beyond stdlib."""

VERSION = "0.1.0"  # keep in sync with pyproject.toml
APP_REPO = "nrathpluk/VoiceInk"  # GitHub owner/repo for auto-update check

DEFAULT_HOTKEY = "ctrl+shift+space"
DEFAULT_MODEL = "base"
MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_LANGUAGE = "th"
LANGUAGES = ["auto", "th", "en"]  # "auto" = let Whisper detect (+0.5-1s)
LANGUAGE_LABELS = {"auto": "Auto-detect", "th": "ไทย (Thai)", "en": "English"}
SAMPLE_RATE = 16000
HISTORY_MAX = 10
APP_NAME = "ThaiVoice"

WIN_W = 320
WIN_H = 64

WAVE_BARS = 10
WAVE_BAR_W = 3
WAVE_BAR_GAP = 4

CAPSULE_RADIUS = 30
MIC_R = 26
MIC_CX = 36
MIC_CY = WIN_H // 2

# Live streaming
LIVE_WINDOW_S = 8.0  # transcribe last N seconds
LIVE_TICK_S = 1.5  # rerun every N seconds
LIVE_COMMIT_TAIL_S = 3.0  # keep last N seconds unconfirmed
LIVE_PREVIEW_H = 76  # extra px when live mode on

# Chroma key for transparent corners (overrideredirect + transparentcolor)
TRANSPARENT_KEY = "#010203"

COLORS = {
    "bg": "#1a1a2e",
    "fg": "#e8e8ea",
    "muted": "#8a8a92",
    "wave_idle": "#4a4a6a",
    "wave_active": "#6C63FF",
    "purple": "#6C63FF",
    "red": "#FF4444",
    "green": "#2ECC71",
    "menu_dot": "#5a5a72",
    "glow": "#2a1d4a",
    "preview_bg": "#15151f",
}
