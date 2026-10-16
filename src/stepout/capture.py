"""Capture: what was said to the model and what it said back, step by step, for debugging. Off unless STEPOUT_CAPTURE=1.

One JSON-lines file per Run under `<Home>/capture/` (`data/capture/` in a checkout). This is the one place a prompt is kept, so its rules are tight: it is never written for a Run that has
read a file or builds on an answer that did (the Runner checks the Run's taint before every call), secret-looking values pass through `redact` first, and
the file goes with its chat (chats.py) or by age (housekeeping.py). The Ledger, not this, is what the page and Evaluation read.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from stepout.model import ModelRequest, ModelResponse
from stepout.redact import redact

_log = logging.getLogger(__name__)


def from_env(folder: Path, environ: Mapping[str, str] = os.environ) -> "Capture | None":
    return Capture(folder) if environ.get("STEPOUT_CAPTURE", "").strip() == "1" else None


class Capture:
    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def write(self, run_id: str, role: str, request: ModelRequest, response: ModelResponse) -> None:
        """Append one model call. Never raises: debugging must not be the reason a Run fails."""
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            line = {
                "at": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "model": request.model,
                "tools": request.tools,
                "sent": redact(request.user_text)[0],  # the system prompt is the Role's own and static: not repeated here
                "received": redact(json.dumps(response.action.model_dump(), ensure_ascii=False))[0],
                "cost_usd": response.cost_usd,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "attempts": response.attempts,
                "duration_ms": response.duration_ms,
            }
            with (self._folder / f"{run_id}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            _log.exception("capture not written")

    def remove(self, run_ids: list[str]) -> None:
        for run_id in run_ids:
            (self._folder / f"{run_id}.jsonl").unlink(missing_ok=True)
