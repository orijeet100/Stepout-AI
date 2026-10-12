"""A Model that fails the way providers do: scripted outcomes in call order, no network.

An outcome is a ModelResponse (returned), a Failure (raised), or a Cut (some words streamed to `on_text`, then a Failure).
"""

from __future__ import annotations

from stepout.failure import Failure
from stepout.model import ModelRequest, ModelResponse


class Cut:
    """A reply that started streaming and was then cut."""

    def __init__(self, words: list[str], failure: Failure) -> None:
        self.words, self.failure = words, failure


class FaultyModel:
    streams = True

    def __init__(self, *outcomes) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[ModelRequest] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def call(self, request: ModelRequest, on_text=None) -> ModelResponse:
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Cut):
            for words in outcome.words:
                if on_text is not None:
                    await on_text(words)
            raise outcome.failure
        if isinstance(outcome, Failure):
            raise outcome
        return outcome
