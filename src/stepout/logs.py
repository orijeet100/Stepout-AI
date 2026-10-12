"""The app log: one rotating file of JSON lines, so a failure outside a Run (or after the terminal is closed) can still be explained.

A line carries the chat and Run it happened in (from `scope`). It never carries what a file or page said: messages are ids, kinds and
sizes, and an exception's own message is written only for types that cannot echo their input (a Pydantic validation error repeats the
value it rejected, which may be file text). The terminal keeps the full traceback, as before.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import anthropic
import httpx

from stepout import scope
from stepout.failure import Failure

LOG_NAME = "stepout.log"
_MAX_BYTES, _BACKUPS = 1_000_000, 5
_MARK = "_stepout_log"
_SAFE_MESSAGE = (Failure, OSError, TimeoutError, httpx.HTTPError, anthropic.APIError)  # their messages are about the world, not about our input
_NOISY = ("httpx", "httpcore", "anthropic", "openai")  # one INFO line per request adds nothing here


class _Lines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if (run := scope.current()) is not None:
            line.update(run_id=run.run_id, conversation_id=run.conversation_id)
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            line["exc_type"] = type(exc).__name__
            if isinstance(exc, _SAFE_MESSAGE):
                line["exc_message"] = str(exc)[:300]
            line["frames"] = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_tb(record.exc_info[2])][-8:]
        return json.dumps(line, ensure_ascii=False)


def configure(directory: Path, environ: Mapping[str, str] = os.environ, max_bytes: int = _MAX_BYTES) -> Path:
    """Send the app's log to `directory/stepout.log` (and warnings to the terminal). Safe to call twice. -> the file's path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOG_NAME
    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, _MARK, False)]:
        root.removeHandler(old)
        old.close()
    level = logging.getLevelName(environ.get("STEPOUT_LOG_LEVEL", "INFO").strip().upper())
    root.setLevel(level if isinstance(level, int) else logging.INFO)
    file = logging.handlers.RotatingFileHandler(path, maxBytes=max_bytes, backupCount=_BACKUPS, encoding="utf-8")
    file.setFormatter(_Lines())
    terminal = logging.StreamHandler(sys.stderr)
    terminal.setLevel(logging.WARNING)
    terminal.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    for handler in (file, terminal):
        setattr(handler, _MARK, True)
        root.addHandler(handler)
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)
    return path
