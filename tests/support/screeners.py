"""A Screener that answers from a script: (decision, cost) pairs, or an Exception to raise. No model, no network."""

from __future__ import annotations

from typing import Sequence

from stepout.domain import Exchange, Proceed


class FixedScreener:
    def __init__(self, *answers) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, list[Exchange]]] = []  # (the message, the Exchanges it was shown)

    async def screen(self, text: str, recent: Sequence[Exchange]):
        self.calls.append((text, list(recent)))
        answer = self._answers.pop(0) if self._answers else (Proceed(), 0.0)
        if isinstance(answer, Exception):
            raise answer
        return answer
