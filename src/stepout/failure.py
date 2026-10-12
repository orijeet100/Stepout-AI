"""A failure the User can be told about in a line: no key, the API is busy, Chrome is missing.

`kind` names the cause (the Ledger keeps it: "auth", "rate_limit", "chrome", ...), `message` is what the User reads (what happened, what to do),
`status` is the HTTP status if there was one. Whether it is worth trying again is retry.py's table, keyed by `kind`. The Runner turns any other exception into a generic line; these say something useful.
"""

from __future__ import annotations


# What the User reads when something fails that no one planned for (a bug, not a Failure): the same words wherever it is caught.
UNEXPECTED = "I hit an unexpected problem and had to stop this task. Nothing on your computer was changed. Try again; if it repeats, the details are in the log (data/logs/stepout.log)."


class Failure(Exception):
    def __init__(self, kind: str, message: str, status: int | None = None, *, retry_after: float | None = None, detail: str = "", cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.kind, self.message, self.status = kind, message, status
        self.retry_after = retry_after  # seconds the provider asked us to wait before trying again, if it said
        self.detail = detail  # what was wrong with a reply: the field and the rule, never the value (it is read back to the model once)
        self.cost_usd = cost_usd  # what a reply that came back unusable was billed
