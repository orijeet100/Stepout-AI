"""The Gate: pure rule functions. No model calls, no I/O — the most tested module.

screen() looks at a Request's text before any money is spent. check() gives a
Verdict for one proposed Action. Both are total: every input gets an answer.
"""

from __future__ import annotations

import re

from stepout.domain import (
    Accept,
    Action,
    AnswerAction,
    Ask,
    DelegateAction,
    Decline,
    FetchAction,
    FilesAction,
    PlanAction,
    Refuse,
    Allow,
    Route,
    Screening,
    SearchAction,
    Unsure,
    Verdict,
)

# Forbidden: refuse outright, regardless of phrasing variety we can't enumerate —
# unmatched-but-risky phrasing is why screen() can also return Unsure.
_FORBIDDEN = [
    (re.compile(r"\bpay\b|\binvoice\b|\btransfer\b|\bpayment\b", re.I), "payments and transfers"),
    (re.compile(r"\bcancel\b|\bcancellation\b", re.I), "cancellations"),
    (re.compile(r"\bdelete\b|\bremove\b.*\baccount\b", re.I), "deletions"),
    (re.compile(r"\bpassword\b|\b2fa\b|\bsecurity\s+question\b", re.I), "password or security changes"),
    (re.compile(r"\bcreate\s+(an?\s+)?account\b|\bsign\s*up\b", re.I), "creating accounts"),
    (re.compile(r"\blog\s*in\b.*\bfor me\b|\benter\s+my\s+(password|credentials)\b", re.I), "tasks needing credentials"),
    (re.compile(r"\bbuild\s+(me\s+)?(a|an|some)\s+(app|website|script|program|software)\b", re.I), "building software"),
]

_ALTERNATIVE = "I can look things up, fetch public pages, and answer questions — just not that."

# Very small signal for routing between Answer and Lookup; anything else is Unsure.
_LOOKUP_HINTS = re.compile(
    r"\bweather\b|\bprice\b|\bnews\b|\btoday\b|\bcurrent\b|\blatest\b|https?://", re.I
)


def screen(request: str) -> Screening:
    for pattern, label in _FORBIDDEN:
        if pattern.search(request):
            return Decline(reason=f"That's {label}, which I won't do.", alternative=_ALTERNATIVE)
    if _LOOKUP_HINTS.search(request):
        return Accept(route=Route.LOOKUP)
    if len(request.split()) <= 3 and "?" not in request:
        # too short to confidently classify without a model call
        return Unsure()
    return Accept(route=Route.ANSWER)


def check(action: Action, allowed: frozenset[str] | None = None) -> Verdict:
    """`allowed` = the Action kinds the acting Role may take (None = no Role restriction)."""
    if allowed is not None and action.kind not in allowed:
        return Refuse(reason=f"a {action.kind} action is not available to this role")
    match action:
        case FetchAction() | SearchAction() | AnswerAction() | PlanAction() | DelegateAction() | FilesAction():
            return Allow()
        case _:  # pragma: no cover - Action is a closed union today
            return Ask(reason="unrecognized action")
