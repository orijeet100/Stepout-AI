"""The front door's labeled prompts (tests/data/screening_prompts.jsonl) and the scoring of a Screener against them.

The scoring is tested offline with stub screeners (tests/test_screening_prompts.py); the live run against Haiku is tests/test_live_screening.py.
A row: {prompt, expect: decline|chat|proceed, tag, related?: [exchange numbers], history?: [{request, reply}]}; `history` is the chat so far, numbered from 1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from stepout.domain import Exchange

PROMPTS = Path(__file__).resolve().parents[1] / "data" / "screening_prompts.jsonl"

# Proposed bars (docs/plan/main-worktree.md, B3): tune after the first live run and log the change.
MIN_AGREEMENT = 0.90
MAX_MEAN_COST = 0.003  # dollars per screening
MAX_FALSE_DECLINES_ON_DEMOS = 0


def load_rows() -> list[dict]:
    return [json.loads(line) for line in PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def exchanges_of(row: dict) -> list[Exchange]:
    return [Exchange(id=n, request=h["request"], reply=h["reply"], did="", run_id=f"r{n}") for n, h in enumerate(row.get("history", []), start=1)]


@dataclass
class Scored:
    row: dict
    got: str  # decline | chat | proceed | fallback (no usable answer)
    related: list[int]
    cost: float
    raw: object = None  # the model's raw answer, when the screener keeps it (HaikuScreener.last_answer): why a row went the way it did

    @property
    def agrees(self) -> bool:
        if self.got != self.row["expect"]:
            return False
        return self.got != "proceed" or "related" not in self.row or sorted(self.related) == sorted(self.row["related"])


async def evaluate(screener, rows: list[dict]) -> list[Scored]:
    scored = []
    for row in rows:
        result, cost = await screener.screen(row["prompt"], exchanges_of(row))
        scored.append(Scored(row, "fallback" if result is None else result.kind, list(getattr(result, "related", [])), cost, getattr(screener, "last_answer", None)))
    return scored


def summarize(scored: list[Scored]) -> dict:
    wrongly_declined = [s for s in scored if s.row["expect"] != "decline" and s.got == "decline"]
    return {
        "agreement": sum(s.agrees for s in scored) / len(scored),
        "false_declines": [s.row["prompt"] for s in wrongly_declined],
        "demo_false_declines": [s.row["prompt"] for s in wrongly_declined if s.row["tag"] == "demo"],
        "fallbacks": [s.row["prompt"] for s in scored if s.got == "fallback"],
        "mean_cost": sum(s.cost for s in scored) / len(scored),
    }
