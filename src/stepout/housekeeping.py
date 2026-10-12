"""Housekeeping: things the app writes that nobody deletes. Today: a Run's screenshots (one folder each) and Capture files, by age."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Mapping

_log = logging.getLogger(__name__)

DEFAULT_DAYS = 30  # a starting value: screenshots are for looking back at a Run, not for keeping


def retention_days(environ: Mapping[str, str] = os.environ) -> int:
    value = environ.get("STEPOUT_RETENTION_DAYS", "").strip()
    return int(value) if value.isdigit() and int(value) > 0 else DEFAULT_DAYS


def sweep(folder: Path, days: int, now: float | None = None) -> int:
    """Remove what is directly in `folder` and has not been touched for `days` days (a folder with everything in it). -> how many. A missing folder is fine."""
    if not folder.is_dir():
        return 0
    cutoff = (time.time() if now is None else now) - days * 86_400
    removed = 0
    for child in folder.iterdir():
        try:
            if child.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
            removed += 1
        except OSError:
            _log.warning("could not remove %s", child.name)  # in use, or already gone: the next start tries again
    return removed
