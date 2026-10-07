"""Domain types: Message, Reply, Task, Run, Action, Result, Verdict, Outcome, Event.

Plain Pydantic models only — no behaviour, no live objects or callbacks (N12:
Actions and Results must round-trip through JSON so hands can later run elsewhere).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Route(StrEnum):
    ANSWER = "answer"  # no tools
    LOOKUP = "lookup"  # fetch or search


class Outcome(StrEnum):
    DONE = "done"
    BLOCKED = "blocked"
    DECLINED = "declined"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    UNCERTAIN = "uncertain"


class Message(BaseModel):
    """One unit of text sent in a Conversation, in either direction."""

    id: str = Field(default_factory=_id)
    user_id: str
    text: str
    at: datetime = Field(default_factory=_now)


class Reply(BaseModel):
    text: str


class Task(BaseModel):
    """An accepted Request the Assistant is responsible for finishing."""

    id: str = Field(default_factory=_id)
    user_id: str
    request: str
    route: Route
    created_at: datetime = Field(default_factory=_now)


class Run(BaseModel):
    """One attempt at carrying out a Task."""

    id: str = Field(default_factory=_id)
    task_id: str
    outcome: Outcome | None = None
    cost_usd: float = 0.0


# --- Actions the model may propose, and their Results --------------------


class FetchAction(BaseModel):
    kind: Literal["fetch"] = "fetch"
    url: str


class SearchAction(BaseModel):
    kind: Literal["search"] = "search"
    query: str


class AnswerAction(BaseModel):
    """No tool use — the model answers directly."""

    kind: Literal["answer"] = "answer"
    text: str


class PlanStep(BaseModel):
    role: Literal["direct"]  # widen as Roles gain hands (files, browser, reader)
    goal: str
    status: Literal["pending", "running", "done", "failed"] = "pending"


class PlanAction(BaseModel):
    """The Orchestrator writes (or rewrites) its Plan."""

    kind: Literal["plan"] = "plan"
    steps: list[PlanStep]


class DelegateAction(BaseModel):
    """The Orchestrator runs one step of its Plan by index; the step's Role does the work."""

    kind: Literal["delegate"] = "delegate"
    step: int


Action = FetchAction | SearchAction | AnswerAction | PlanAction | DelegateAction


class FetchResult(BaseModel):
    kind: Literal["fetch"] = "fetch"
    url: str
    text: str


class SearchResult(BaseModel):
    kind: Literal["search"] = "search"
    query: str
    snippets: list[str]


class AnswerResult(BaseModel):
    kind: Literal["answer"] = "answer"
    text: str


Result = FetchResult | SearchResult | AnswerResult


# --- Gate ------------------------------------------------------------------


class Accept(BaseModel):
    kind: Literal["accept"] = "accept"
    route: Route


class Decline(BaseModel):
    kind: Literal["decline"] = "decline"
    reason: str
    alternative: str


class Unsure(BaseModel):
    kind: Literal["unsure"] = "unsure"


Screening = Accept | Decline | Unsure


class Allow(BaseModel):
    kind: Literal["allow"] = "allow"


class Ask(BaseModel):
    kind: Literal["ask"] = "ask"
    reason: str


class Refuse(BaseModel):
    kind: Literal["refuse"] = "refuse"
    reason: str


Verdict = Allow | Ask | Refuse


# --- Ledger ------------------------------------------------------------------


class Event(BaseModel):
    """One append-only Ledger row."""

    id: str = Field(default_factory=_id)
    task_id: str | None = None
    run_id: str | None = None
    kind: str  # "screening" | "plan" | "step" | "return" | "stop"
    role: str | None = None  # which Role acted
    parent: str | None = None  # the Delegate step event that started this Role's work
    data: dict
    cost_usd: float = 0.0
    at: datetime = Field(default_factory=_now)
