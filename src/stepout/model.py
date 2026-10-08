"""Model port: Protocol + Anthropic provider adapter.

Pricing is hardcoded ($/Mtok) rather than fetched, per ADR 0001 (borrow
plumbing, don't wrap it) — update PRICING when Anthropic's list prices change.

The port is stateless: one request in, one Action out. Roles pass a compact
state string, not a transcript. Tool choice is left to the model (forced tool
use is rejected by newer models); a text-only reply is treated as the answer.
"""

from __future__ import annotations

from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel

from stepout import capabilities
from stepout.capabilities.base import tool_schema
from stepout.domain import Action, AnswerAction, DelegateAction, PlanAction
from stepout.roles import HAIKU, SONNET, SPECIALISTS

# $ per million tokens: (input, output). Web search billed separately, per use.
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (3.00, 15.00),
}
WEB_SEARCH_COST_PER_USE = 10.00 / 1000

# The Orchestrator's own tools. Every other tool comes from the capability registry.
_CONTROL_TOOLS = {
    t["name"]: t
    for t in [
        tool_schema(
            "plan",
            "Write your plan: 1-3 steps, each run by one role. Calling it again replaces the plan.",
            steps={
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {"role": {"type": "string", "enum": list(SPECIALISTS)}, "goal": {"type": "string"}},
                    "required": ["role", "goal"],
                },
            },
        ),
        tool_schema("delegate", "Run one step of your plan by its number (0 is the first). Its Finding comes back next turn.", step={"type": "integer", "minimum": 0}),
        tool_schema("answer", "Give the final reply to the user.", text={"type": "string"}),
    ]
}


class ModelRequest(BaseModel):
    model: str
    system: str
    user_text: str
    tools: list[str] = []  # "web_search" or a client tool name; none = a plain completion
    tool_defs: list[dict] = []  # one-off tools, sent as they are; a call to one comes back as a ToolCall (the front door's `screen`)
    max_searches: int = 3  # web searches this Run may still use


class ToolCall(BaseModel):
    """The model called a one-off tool from `ModelRequest.tool_defs`; the caller reads `input` (untrusted, unvalidated)."""

    kind: Literal["tool_call"] = "tool_call"
    name: str
    input: dict


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
        tool = _CONTROL_TOOLS.get(name) or capabilities.get(name).tool
        if name != "web_search":
            defs.append(tool)
        elif request.max_searches > 0:  # the provider runs searches; this Run's remaining count caps them
            defs.append({**tool, "max_uses": request.max_searches})
    return defs + request.tool_defs


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


def _action(content, one_off: frozenset[str] = frozenset()) -> Action:
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
        if tool.name in one_off:
            return ToolCall(name=tool.name, input=dict(args))
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
        one_off = frozenset(d["name"] for d in request.tool_defs)
        return ModelResponse(action=_action(response.content, one_off), cost_usd=cost, searches=searches)
