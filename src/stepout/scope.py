"""The scope of one Run: who is acting and what a model call may use, carried in a context variable.

The Runner sets it for the length of `submit`. Anything running inside it (the model port's retries, the log's ids) reads it with `current()`;
a call made outside a Run (Screening) sees `None` and does without. A context variable, not a parameter, so the `Model` protocol and every
fake of it stay as they are. A task started inside the Run (`_unless_stopped`) inherits it.
"""

from __future__ import annotations

import math
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


async def _nothing(*args: Any, **kwargs: Any) -> None:
    return None


@dataclass
class RunScope:
    run_id: str
    task_id: str
    conversation_id: str
    emit: Callable[..., Awaitable[Any]] = _nothing  # emit(kind, summary, **data): a Trace event of this Run, under the Role acting
    reset_stream: Callable[[], Awaitable[None]] = _nothing  # tell the page to drop the words streamed so far (they were not the answer)
    budget_left: Callable[[], float] = lambda: math.inf  # dollars the Run may still spend
    retries: int = 0  # model-call retries so far in this Run
    retry_wait_s: float = 0.0  # seconds spent waiting between them
    repairs: int = 0  # replies repaired so far


_RUN: ContextVar[RunScope | None] = ContextVar("stepout_run", default=None)


def current() -> RunScope | None:
    return _RUN.get()


def enter(scope: RunScope) -> Token:
    return _RUN.set(scope)


def leave(token: Token) -> None:
    _RUN.reset(token)
