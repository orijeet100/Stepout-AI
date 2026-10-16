"""Home: the one folder that holds the User's chats, Memory, settings, key and log. Every data path derives from `home()`."""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
CHECKOUT = _ROOT if (_ROOT / "pyproject.toml").is_file() and (_ROOT / "src" / "stepout").is_dir() else None  # the source checkout this runs from, if any


def home() -> Path:
    """STEPOUT_HOME if set; else `data/` in a source checkout (development is unchanged); else the per-user app folder,
    so an installed copy never writes into the working directory or the package, and an upgrade keeps everything.
    (Elsewhere than Windows the fallback is `$XDG_DATA_HOME/Stepout`, else `~/.local/share/Stepout`: the app is not supported there yet.)"""
    if env := os.environ.get("STEPOUT_HOME"):
        return Path(env).expanduser().resolve()
    if CHECKOUT is not None:
        return CHECKOUT / "data"
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "Stepout"
