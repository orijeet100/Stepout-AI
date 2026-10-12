"""Model port: Protocol + Anthropic provider adapter.

Pricing is hardcoded ($/Mtok) rather than fetched, per ADR 0001 (borrow
plumbing, don't wrap it) — update PRICING when Anthropic's list prices change.

The port is stateless: one request in, one Action out. Roles pass a compact
state string, not a transcript. Tool choice is left to the model (forced tool
use is rejected by newer models); a text-only reply is treated as the answer.
"""

from __future__ import annotations

import json
import re
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from stepout import capabilities
from stepout.capabilities.base import tool_schema
from stepout.domain import Action, AnswerAction, DelegateAction, PlanAction
from stepout.failure import Failure
from stepout.roles import HAIKU, SONNET, SPECIALISTS

# $ per million tokens: (input, output). Web search billed separately, per use.
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (2.00, 10.00),  # Sonnet 5's list price; its introductory rate was made permanent in August 2026. Check Anthropic's pricing page when it changes
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
    tools: list[str] = []  # control tool or capability names, offered as function tools; none = a plain completion
    tool_defs: list[dict] = []  # one-off tools, sent as they are; a call to one comes back as a ToolCall (Screening's `screen`)
    temperature: float | None = None  # None = the API default (1.0). Models released after Opus 4.6 reject any other value with a 400: of ours only HAIKU (4.5) accepts one, SONNET (5) does not
    search: bool = False  # let the provider run its own web search in this call (only the Searcher asks); `max_searches` caps it
    max_searches: int = 3  # web searches this call may run, when `search` is set


class ToolCall(BaseModel):
    """The model called a one-off tool from `ModelRequest.tool_defs`; the caller reads `input` (untrusted, unvalidated)."""

    kind: Literal["tool_call"] = "tool_call"
    name: str
    input: dict


class ModelResponse(BaseModel):
    action: BaseModel  # any Action; not the closed `Action` union, which cannot know a capability registered after import
    cost_usd: float
    searches: int = 0  # web searches this call used
    input_tokens: int = 0  # what the provider billed, from its own usage figures
    output_tokens: int = 0
    attempts: int = 1  # tries it took (retry.py fills it); 1 = no retry
    duration_ms: int = 0  # the successful try, from send to the finished reply (retry.py fills it)


class Model(Protocol):
    async def call(self, request: ModelRequest) -> ModelResponse: ...


def _cost(model: str, input_tokens: int, output_tokens: int, web_searches: int) -> float:
    in_rate, out_rate = PRICING[model]
    return (
        input_tokens * in_rate / 1_000_000
        + output_tokens * out_rate / 1_000_000
        + web_searches * WEB_SEARCH_COST_PER_USE
    )


# The basic version: 20260209+ defaults to dynamic filtering via code execution, which Haiku can't use. `max_uses` is added per request.
_NATIVE_SEARCH = {"type": "web_search_20250305", "name": "web_search"}


def _tool_defs(request: ModelRequest) -> list[dict]:
    defs = [_CONTROL_TOOLS.get(name) or capabilities.get(name).tool for name in request.tools]
    if request.search and request.max_searches > 0:  # the provider runs the search; the Searcher's call asks for one
        defs.append({**_NATIVE_SEARCH, "max_uses": request.max_searches})
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


def client_tools(request: ModelRequest) -> list[dict]:
    """The tools every provider is offered as plain functions (name, description, input_schema)."""
    return [_CONTROL_TOOLS.get(name) or capabilities.get(name).tool for name in request.tools] + request.tool_defs


def call_to_action(name: str, args: dict, one_off: frozenset[str] = frozenset()):
    """A model's tool call as our Action (or a ToolCall for a one-off tool); None if `name` is not a tool we offered. Shared by every provider adapter."""
    if (parsed := capabilities.parse(name, args)) is not None:
        return parsed
    match name:
        case "plan":
            return PlanAction(steps=args["steps"])
        case "delegate":
            return DelegateAction(step=args["step"])
        case "answer":
            return AnswerAction(text=args["text"])
    if name in one_off:
        return ToolCall(name=name, input=dict(args))
    return None


def _partial_text(partial_json: str) -> str:
    """The `text` string of a JSON object that is still being written, as far as it has arrived: a half-written escape waits for its other half."""
    start = re.search(r'"text"\s*:\s*"', partial_json)
    if start is None:
        return ""
    raw, i = partial_json[start.end() :], 0
    while i < len(raw) and raw[i] != '"':
        if raw[i] == "\\":
            need = 6 if raw[i + 1 : i + 2] == "u" else 2
            if i + need > len(raw):
                break
            i += need
        else:
            i += 1
    body = re.sub(r"\\u[dD][89abAB][0-9a-fA-F]{2}$", "", raw[:i])  # the first half of a surrogate pair waits for the second
    return json.loads('"' + body + '"')


def _action(content, one_off: frozenset[str] = frozenset()) -> Action:
    tool = next((b for b in content if b.type == "tool_use"), None)
    if tool is not None and (action := call_to_action(tool.name, tool.input, one_off)) is not None:
        return action
    text = "".join(b.text for b in content if b.type == "text")
    return AnswerAction(text=text + _sources(content))


_WAIT = "Wait a minute, then send it again."
_KEY_FIX = "Check ANTHROPIC_API_KEY in the .env file, then restart the app."


def malformed_detail(exc: Exception) -> str:
    """What was wrong with a reply, for the model to read back once: the field and the rule, never the value (it may be text from a file)."""
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}" for e in exc.errors(include_input=False, include_url=False))[:300]
    if isinstance(exc, KeyError) and exc.args:
        return f"missing {exc.args[0]!r}"
    return type(exc).__name__


def _retry_after(exc: Exception) -> float | None:
    """Seconds the provider asked us to wait (its Retry-After header, in seconds), if it said."""
    try:
        seconds = float(exc.response.headers.get("retry-after"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _explain(exc: anthropic.APIError) -> Failure:
    """The API said no, or could not be reached: one line for the User and the cause for the Ledger. (No retry has happened here: the SDK's are off; retry.py owns them.)"""
    status = getattr(exc, "status_code", None)
    wait = _retry_after(exc)
    match exc:
        case anthropic.AuthenticationError() | anthropic.PermissionDeniedError():
            return Failure("auth", f"Anthropic rejected the API key ({status}). {_KEY_FIX}", status)
        case anthropic.RateLimitError():
            return Failure("rate_limit", f"Anthropic is rate-limiting requests right now ({status}). {_WAIT}", status, retry_after=wait)
        case anthropic.OverloadedError():
            return Failure("overloaded", f"Anthropic is overloaded right now ({status}). {_WAIT}", status, retry_after=wait)
        case anthropic.InternalServerError():
            return Failure("server_error", f"Anthropic had a server error ({status}). Try again in a minute.", status, retry_after=wait)
        case anthropic.APITimeoutError():
            return Failure("timeout", "The request to Anthropic timed out. Try again.")
        case anthropic.APIConnectionError():
            return Failure("connection", "Could not reach Anthropic. Check your internet connection, then try again.")
        case anthropic.APIStatusError() if "credit balance" in str(getattr(exc, "message", "")).lower():
            return Failure("credit", "Your Anthropic account is out of credit. Add credit at console.anthropic.com, then try again.", status)
        case _:
            return Failure("rejected", f"Anthropic rejected the request ({status}). Try again; if it repeats, tell the developer.", status)


class AnthropicModel:
    streams = True  # `call` can hand the words of a reply to `on_text` as they arrive

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(max_retries=0)  # the SDK's own retries are off: retry.py's policy is the only one, and records every attempt

    async def call(self, request: ModelRequest, on_text=None) -> ModelResponse:
        if not self._client.api_key:  # the SDK would only fail later, inside the request, with a TypeError
            raise Failure("no_key", "There is no Anthropic API key. Put ANTHROPIC_API_KEY=... in the .env file (copy .env.example), then restart the app.")
        # Omit `tools` entirely when unused: tools=None is sent as null and the API rejects it.
        defs = _tool_defs(request)
        if on_text is not None:  # by default a tool call's arguments are buffered and arrive whole; this asks for the reply's words as they are written
            defs = [{**d, "eager_input_streaming": True} if d.get("name") == "answer" else d for d in defs]
        extra = {"tools": defs} if defs else {}
        if request.temperature is not None:  # never send null: only set it when asked
            extra["extra_body"] = {"temperature": request.temperature}  # in the body: SDK 1.x has no `temperature` argument on create() (a TypeError); the body takes it on every version
        params = dict(model=request.model, max_tokens=4096, system=request.system, messages=[{"role": "user", "content": request.user_text}], **extra)
        try:
            response = await self._client.messages.create(**params) if on_text is None else await self._stream(params, on_text)
        except anthropic.APIError as exc:
            raise _explain(exc) from exc
        cost = 0.0
        try:
            # ponytail: a long search can end with stop_reason "pause_turn"; we return the partial text instead of resuming.
            searches = sum(1 for b in response.content if b.type == "web_search_tool_result")
            cost = _cost(request.model, response.usage.input_tokens, response.usage.output_tokens, searches)
            one_off = frozenset(d["name"] for d in request.tool_defs)
            return ModelResponse(
                action=_action(response.content, one_off), cost_usd=cost, searches=searches,
                input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
            )
        except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:  # a body that is not a message, or a tool call missing its arguments
            raise Failure(
                "malformed", "Anthropic's reply could not be understood. Try again; if it repeats, tell the developer.",
                detail=malformed_detail(exc), cost_usd=cost,  # the reply came back, so it was billed
            ) from exc

    async def _stream(self, params: dict, on_text):
        """The same request, streamed. The words of a text reply, and the growing `text` of the `answer` tool, go to `on_text` as they arrive;
        the finished message comes back exactly as `create` would give it, so nothing after this changes."""
        tool, sent, partial = None, 0, ""
        async with self._client.messages.stream(**params) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    tool, sent, partial = (event.content_block.name if event.content_block.type == "tool_use" else None), 0, ""
                elif event.type == "text":
                    await on_text(event.text)
                elif event.type == "input_json" and tool == "answer":
                    partial += event.partial_json  # not the SDK's `snapshot`: it leaves a string out until its closing quote has arrived
                    words = _partial_text(partial)
                    if len(words) > sent:
                        await on_text(words[sent:])
                        sent = len(words)
            return await stream.get_final_message()
