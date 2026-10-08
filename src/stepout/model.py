"""Model port: Protocol + Anthropic provider adapter.

Pricing is hardcoded ($/Mtok) rather than fetched, per ADR 0001 (borrow
plumbing, don't wrap it) — update PRICING when Anthropic's list prices change.

The port is stateless: one request in, one Action out. Roles pass a compact
state string, not a transcript. Tool choice is left to the model (forced tool
use is rejected by newer models); a text-only reply is treated as the answer.
"""

from __future__ import annotations

from typing import Protocol

import anthropic
from pydantic import BaseModel

from stepout import capabilities
from stepout.capabilities.base import tool_schema as _tool
from stepout.domain import Action, AnswerAction, DelegateAction, PlanAction

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"

# $ per million tokens: (input, output). Web search billed separately, per use.
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (3.00, 15.00),
}
WEB_SEARCH_COST_PER_USE = 10.00 / 1000

# Basic web search: 20260209+ defaults to dynamic filtering via code execution, which Haiku can't use.
_WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search"}


_CLIENT_TOOLS = {
    t["name"]: t
    for t in [
        _tool(
            "plan",
            "Write your plan: 1-3 steps, each run by one role. Calling it again replaces the plan.",
            steps={
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {"role": {"type": "string", "enum": ["direct", "files", "browser"]}, "goal": {"type": "string"}},
                    "required": ["role", "goal"],
                },
            },
        ),
        _tool("delegate", "Run one step of your plan by its number (0 is the first). Its Finding comes back next turn.", step={"type": "integer", "minimum": 0}),
        _tool("answer", "Give the final reply to the user.", text={"type": "string"}),
    ]
}


class ModelRequest(BaseModel):
    model: str
    system: str
    user_text: str
    tools: list[str] = []  # "web_search" or a client tool name; none = a plain completion
    max_searches: int = 3  # web searches this Run may still use


class ModelResponse(BaseModel):
    action: BaseModel  # any Action; not the closed `Action` union, which cannot know a capability registered after import
    cost_usd: float
    searches: int = 0  # web searches this call used


class Model(Protocol):
    async def call(self, request: ModelRequest) -> ModelResponse: ...


def _cost(model: str, input_tokens: int, output_tokens: int, web_searches: int) -> float:
    in_rate, out_rate = PRICING[model]
    return (
        input_tokens * in_rate / 1_000_000
        + output_tokens * out_rate / 1_000_000
        + web_searches * WEB_SEARCH_COST_PER_USE
    )


def _tool_defs(request: ModelRequest) -> list[dict]:
    defs = []
    for name in request.tools:
        if name != "web_search":
            defs.append(_CLIENT_TOOLS.get(name) or capabilities.get(name).tool)
        elif request.max_searches > 0:
            defs.append({**_WEB_SEARCH, "max_uses": request.max_searches})
    return defs


def _sources(content) -> str:
    """The cited pages, as markdown links, so answers keep their sources."""
    cited: dict[str, str] = {}
    for block in content:
        for c in getattr(block, "citations", None) or []:
            if url := getattr(c, "url", None):
                cited.setdefault(url, getattr(c, "title", None) or url)
    if not cited:
        return ""
    return "\n\nSources:\n" + "\n".join(f"- [{title}]({url})" for url, title in list(cited.items())[:8])


def _action(content) -> Action:
    tool = next((b for b in content if b.type == "tool_use"), None)
    if tool is not None:
        args = tool.input
        if (parsed := capabilities.parse(tool.name, args)) is not None:
            return parsed
        match tool.name:
            case "plan":
                return PlanAction(steps=args["steps"])
            case "delegate":
                return DelegateAction(step=args["step"])
            case "answer":
                return AnswerAction(text=args["text"])
    text = "".join(b.text for b in content if b.type == "text")
    return AnswerAction(text=text + _sources(content))


class AnthropicModel:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()

    async def call(self, request: ModelRequest) -> ModelResponse:
        # Omit `tools` entirely when unused: tools=None is sent as null and the API rejects it.
        defs = _tool_defs(request)
        extra = {"tools": defs} if defs else {}
        response = await self._client.messages.create(
            model=request.model,
            max_tokens=4096,
            system=request.system,
            messages=[{"role": "user", "content": request.user_text}],
            **extra,
        )
        # ponytail: a long search can end with stop_reason "pause_turn"; we return the partial text instead of resuming.
        searches = sum(1 for b in response.content if b.type == "web_search_tool_result")
        cost = _cost(request.model, response.usage.input_tokens, response.usage.output_tokens, searches)
        return ModelResponse(action=_action(response.content), cost_usd=cost, searches=searches)
