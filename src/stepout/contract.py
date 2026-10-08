"""The wire types of docs/ui-contract.md v1, as Pydantic models: what the page and the backend promise each other.

This file and that document move together: a change to either needs the other and a `contract` entry in docs/log/.
`extra="forbid"` is deliberate: a field a test fixture has and these models lack is drift, and the test should say so.
(The page, for its part, must ignore unknown fields and kinds; additive changes are free.)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- page -> server (WebSocket) -------------------------------------------------


class SendFrame(_Wire):
    type: Literal["send"] = "send"
    conversation_id: str
    text: str


class StopFrame(_Wire):
    type: Literal["stop"] = "stop"


ClientFrame = Annotated[SendFrame | StopFrame, Field(discriminator="type")]


# --- server -> page (WebSocket); every frame but hello has `at` -------------------


class HelloFrame(_Wire):
    type: Literal["hello"] = "hello"
    v: int = 1


class MessageFrame(_Wire):
    type: Literal["message"] = "message"
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    text: str
    run_id: str | None = None  # assistant only
    cost_usd: float | None = None  # assistant only
    at: datetime


class TraceFrame(_Wire):
    """One Ledger event of a Run, live or replayed: plan, step, return, shot or stop. `data` varies by `kind` (see the contract's table)."""

    type: Literal["trace"] = "trace"
    id: str
    conversation_id: str
    run_id: str
    parent: str | None  # the `step` event that started this Role's work
    kind: str
    role: str | None
    data: dict
    cost_usd: float = 0.0
    at: datetime


class Active(_Wire):
    conversation_id: str
    run_id: str
    cap_usd: float


class Queued(_Wire):
    conversation_id: str


class StatusFrame(_Wire):
    type: Literal["status"] = "status"
    state: Literal["idle", "running"]
    active: Active | None
    queued: list[Queued]
    at: datetime


ServerFrame = Annotated[HelloFrame | MessageFrame | TraceFrame | StatusFrame, Field(discriminator="type")]


# --- HTTP (JSON) ------------------------------------------------------------------


class ConversationSummary(_Wire):
    """GET /api/conversations (newest first). `state` is the Runner's view of the queue as well; the database alone can say idle or running."""

    id: str
    title: str
    updated_at: datetime
    preview: str
    state: Literal["idle", "queued", "running"]


class RunSummary(_Wire):
    run_id: str
    request: str
    state: Literal["running", "done", "stopped", "failed"]  # an over-budget Run is `stopped`; the reason is in its `stop` event
    cost_usd: float
    cap_usd: float
    steps: int
    started_at: datetime
    ended_at: datetime | None


class ConversationDetail(_Wire):
    """GET /api/conversations/{id}."""

    id: str
    title: str
    messages: list[MessageFrame]
    runs: list[RunSummary]


class NewConversation(_Wire):
    """POST /api/conversations."""

    id: str
