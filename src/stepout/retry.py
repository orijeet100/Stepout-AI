"""The one retry policy for every model call (ADR 0015).

`RetryingModel` wraps the Model port once, at the composition root, so the Runner, Screening and the Searcher all follow the same table and
both adapters (their SDK retries are switched off) have exactly one owner. A call made inside a Run (see scope.py) records every attempt as a
`retry` event, counts against the Run's bounds and its budget, and can tell the page to drop words it streamed before a cut; a call outside a
Run (Screening) gets the same attempts and waits and is only logged.

Stop needs nothing here: the Runner awaits the call through `_unless_stopped`, so a cancel ends the wait where it is.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Callable

from stepout import scope as run_scope
from stepout.backoff import RETRY_AFTER_CEILING_S, wait
from stepout.failure import Failure
from stepout.model import PRICING, Model, ModelRequest, ModelResponse

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    attempts: int  # in all, the first try included
    base_s: float  # wait before the second try; doubles after that
    cap_s: float


# The starting values of the table in docs/brainstorms/2026-10-11-record-and-memory-requirements.md (R22): calibrate with the fault tests
# and the first live run. A kind that is not here is never retried.
_TRANSIENT = Rule(attempts=3, base_s=1.0, cap_s=8.0)
RULES = {kind: _TRANSIENT for kind in ("rate_limit", "overloaded", "server_error", "timeout", "connection")}
STREAM_CUT_ATTEMPTS = 2  # words had already reached the page: one more try, after the page drops them
RUN_MAX_RETRIES = 8  # all model-call retries of one Run together
RUN_MAX_WAIT_S = 60.0
REPAIRS_PER_RUN = 3  # replies re-asked after being unreadable, all calls of one Run together (one per call)
_REPAIR = "Your last reply could not be used: {why}. Reply again with exactly one tool call that has every required argument."

_SHORT = {
    "rate_limit": "The provider is rate-limiting requests",
    "overloaded": "The provider is busy",
    "server_error": "The provider had a server error",
    "timeout": "The request timed out",
    "connection": "Could not reach the provider",
}


def _human(seconds: float) -> str:
    return f"{round(seconds / 60)} minutes" if seconds >= 90 else f"{round(seconds)} seconds"


class RetryingModel:
    def __init__(self, inner: Model, *, sleep=asyncio.sleep, rng: Callable[[], float] = random.random, clock: Callable[[], float] = time.monotonic) -> None:
        """`sleep`, `rng` and `clock` are there so a test can run the whole table without waiting."""
        self._inner, self._sleep, self._rng, self._clock = inner, sleep, rng, clock

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner, name)  # `streams`, `target`, `key_vars`: what the inner model declares

    async def call(self, request: ModelRequest, on_text=None) -> ModelResponse:
        run = run_scope.current()
        streamed = False  # words of the attempt in progress have reached `on_text`

        async def watched(words: str) -> None:
            nonlocal streamed
            streamed = streamed or bool(words)
            await on_text(words)

        attempt, repaired = 0, False
        while True:
            attempt += 1
            streamed = False
            began = self._clock()
            try:
                response = await (self._inner.call(request, on_text=watched) if on_text is not None else self._inner.call(request))
            except Failure as failure:
                if failure.kind == "malformed" and not repaired and (run is None or (run.repairs < REPAIRS_PER_RUN and run.budget_left() > 0)):
                    repaired = True  # one repair per call: say what was wrong (the field and the rule, never the value) and ask again
                    if run is not None:
                        run.repairs += 1
                        run.charge(failure.cost_usd)  # the unreadable reply was billed
                        await run.emit("retry", "The reply could not be used; asking again", cost=failure.cost_usd, attempt=attempt, of=attempt + 1, cause="malformed", status=None, wait_s=0.0, repair=True)
                    _log.warning("model reply unreadable (%s), asking again", failure.detail)
                    why = failure.detail or "it was not a valid tool call"
                    request = request.model_copy(update={"user_text": request.user_text + "\n\n" + _REPAIR.format(why=why)})
                    continue
                plan = self._next(failure, attempt, streamed, run, request)
                if plan is None:
                    if run is not None and failure.cost_usd:
                        run.charge(failure.cost_usd)  # an unreadable reply that ends the call was still billed
                    raise
                delay, allowed, cost = plan
                if streamed and run is not None:
                    await run.reset_stream()  # what came so far was not the answer: the page drops it, the next try writes it again
                if run is not None:
                    run.retries += 1
                    run.retry_wait_s += delay
                    run.charge(cost)
                    await run.emit(
                        "retry", f"{_SHORT[failure.kind]}; trying again in {delay:g} s ({attempt + 1} of {allowed})", cost=cost,
                        attempt=attempt, of=allowed, cause=failure.kind, status=failure.status, wait_s=delay,
                    )
                _log.warning("model call failed (%s, status %s), try %d of %d in %gs", failure.kind, failure.status, attempt + 1, allowed, delay)
                await self._sleep(delay)
                continue
            return response.model_copy(update={"attempts": attempt, "duration_ms": round((self._clock() - began) * 1000)})

    def _next(self, failure: Failure, attempt: int, streamed: bool, run: run_scope.RunScope | None, request: ModelRequest) -> tuple[float, int, float] | None:
        """(wait, attempts allowed, cost of the failed attempt) if it is worth another try; None if not. Raises when the provider's own wait is too long to take."""
        rule = RULES.get(failure.kind)
        if rule is None or (streamed and run is None):  # (words on a page that nobody can tell to drop them)
            return None
        allowed = STREAM_CUT_ATTEMPTS if streamed else rule.attempts
        if attempt >= allowed:
            return None
        if failure.retry_after is not None and failure.retry_after > RETRY_AFTER_CEILING_S:
            raise Failure(
                failure.kind, f"{failure.message.rstrip('.')}. It asks for about {_human(failure.retry_after)} before the next request.",
                failure.status, retry_after=failure.retry_after,
            ) from failure
        if failure.retry_after is not None:
            delay = failure.retry_after
        else:
            delay = wait(attempt, rule.base_s, rule.cap_s, self._rng)
        if run is not None and (run.retries >= RUN_MAX_RETRIES or run.retry_wait_s + delay > RUN_MAX_WAIT_S or run.budget_left() <= 0):
            return None
        # ponytail: a cut stream is charged an estimate of its input only (about 4 characters a token, tool definitions not counted); the provider's billing of a cut stream is not known.
        in_rate = PRICING.get(request.model, (0.0, 0.0))[0]
        cost = (len(request.system) + len(request.user_text)) / 4 * in_rate / 1_000_000 if streamed else 0.0
        return delay, allowed, cost
