"""Model port: Protocol + Anthropic provider adapter.

Pricing is hardcoded ($/Mtok) rather than fetched, per ADR 0001 (borrow
plumbing, don't wrap it) — update PRICING when Anthropic's list prices change.
"""

from __future__ import annotations

from typing import Protocol

import anthropic
from pydantic import BaseModel

from stepout.domain import Action, AnswerAction, FetchAction

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"

# $ per million tokens: (input, output). Web search billed separately, per use.
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (3.00, 15.00),
}
WEB_SEARCH_COST_PER_USE = 10.00 / 1000

_FETCH_TOOL = {
    "name": "fetch",
    "description": "Fetch a URL you already know, when you don't need to search for it first.",
    "input_schema": {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
}
_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


class ModelRequest(BaseModel):
    model: str
    system: str
    user_text: str
    tools: bool = False  # web_search + fetch available


class ModelResponse(BaseModel):
    action: Action
    cost_usd: float


class Model(Protocol):
    async def call(self, request: ModelRequest) -> ModelResponse: ...


def _cost(model: str, input_tokens: int, output_tokens: int, web_searches: int) -> float:
    in_rate, out_rate = PRICING[model]
    return (
        input_tokens * in_rate / 1_000_000
        + output_tokens * out_rate / 1_000_000
        + web_searches * WEB_SEARCH_COST_PER_USE
    )


class AnthropicModel:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()

    async def call(self, request: ModelRequest) -> ModelResponse:
        # Omit `tools` entirely when unused: tools=None is sent as null and the API rejects it.
        extra = {"tools": [_WEB_SEARCH_TOOL, _FETCH_TOOL]} if request.tools else {}
        response = await self._client.messages.create(
            model=request.model,
            max_tokens=4096,
            system=request.system,
            messages=[{"role": "user", "content": request.user_text}],
            **extra,
        )
        web_searches = sum(
            1 for b in response.content if b.type == "web_search_tool_result"
        )
        cost = _cost(request.model, response.usage.input_tokens, response.usage.output_tokens, web_searches)

        fetch_use = next((b for b in response.content if b.type == "tool_use" and b.name == "fetch"), None)
        if fetch_use is not None:
            return ModelResponse(action=FetchAction(url=fetch_use.input["url"]), cost_usd=cost)

        text = "".join(b.text for b in response.content if b.type == "text")
        return ModelResponse(action=AnswerAction(text=text), cost_usd=cost)
