"""Auto-update check. Fetches GitHub latest release, compares to local VERSION.

Background-thread safe. Network errors swallowed (logged, not raised).
"""

import json
import urllib.error
import urllib.request

from constants import APP_REPO, VERSION
from log_setup import log

_API_URL = f"https://api.github.com/repos/{APP_REPO}/releases/latest"
_TIMEOUT_S = 5.0
_USER_AGENT = "ThaiVoice-update-check"


def _normalize(tag: str) -> tuple[int, ...]:
    """Parse 'v1.2.3' or '1.2.3' into (1, 2, 3). Non-numeric parts -> 0.

    Stops at the first non-digit per part so '1.2.3-rc1' -> (1, 2, 3).
    """
    s = tag.strip().lstrip("vV")
    parts = s.split(".")
    out = []
    for p in parts:
        digits = []
        for ch in p:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        out.append(int("".join(digits)) if digits else 0)
    return tuple(out)


def is_newer(remote: str, local: str = VERSION) -> bool:
    """Return True if `remote` represents a strictly newer version than `local`."""
    try:
        return _normalize(remote) > _normalize(local)
    except Exception:
        return False


def fetch_latest_tag() -> str | None:
    """GET latest release tag from GitHub. Returns tag string or None on any error."""
    req = urllib.request.Request(
        _API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        log.info("update check: HTTP %s (no release yet?)", e.code)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.info("update check: network error: %s", e)
        return None
    except Exception:
        log.exception("update check: unexpected error")
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not tag or not isinstance(tag, str):
        return None
    return tag


def check_for_update() -> str | None:
    """Returns the new version tag if a newer one exists, else None.

    Safe to call from a background thread. Never raises.
    """
    tag = fetch_latest_tag()
    if tag is None:
        return None
    if is_newer(tag):
        log.info("update available: %s -> %s", VERSION, tag)
        return tag
    log.info("update check: up to date (latest=%s, local=%s)", tag, VERSION)
    return None
