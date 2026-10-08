"""The Gate: pure rule functions. No model calls, no I/O — the most tested module.

check() gives a Verdict for one proposed Action. It is total: every input gets an answer.
(Screening a Request before any money is spent is the front door's job: stepout/screening.py.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from stepout import capabilities
from stepout.domain import (
    Action,
    AnswerAction,
    Ask,
    DelegateAction,
    PlanAction,
    Refuse,
    Allow,
    SearchAction,
    Verdict,
)

if TYPE_CHECKING:
    from stepout.capabilities.base import RunContext


# What a Run that has read a file is told when it tries the web. File contents are written by anyone and may carry instructions; the web is
# the way out, so it is closed for the rest of the Run (C3 relaxes this to the sites the User named).
_WEB_CLOSED = (
    "the web is closed for the rest of this task: {why}, and what a file holds must never be sent out through a URL. "
    "Work from what you already have, and say plainly what you could not do."
)


def check(action: Action, allowed: frozenset[str] | None = None, ctx: RunContext | None = None) -> Verdict:
    """`allowed` = the Action kinds the acting Role may take (None = no Role restriction). A capability may add its own rule."""
    if allowed is not None and action.kind not in allowed:
        return Refuse(reason=f"a {action.kind} action is not available to this role")
    if (cap := capabilities.get(action.kind)) is not None:
        if cap.reaches_web and ctx is not None and ctx.state.tainted:
            return Refuse(reason=_WEB_CLOSED.format(why=ctx.state.tainted))
        verdict = cap.check(action, ctx)
        return Allow() if verdict is None else verdict
    match action:
        case SearchAction() | AnswerAction() | PlanAction() | DelegateAction():
            return Allow()
        case _:  # pragma: no cover - Action is a closed union today
            return Ask(reason="unrecognized action")
