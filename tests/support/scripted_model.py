"""A Model that returns a pre-programmed sequence of responses. No network calls."""

from __future__ import annotations

from stepout.model import ModelRequest, ModelResponse


class ScriptedModel:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[ModelRequest] = []

    async def call(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self._responses.pop(0)
