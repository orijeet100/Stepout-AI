"""A failure the User can be told about in a line: no key, the API is busy, Chrome is missing.

`kind` names the cause (the Ledger keeps it: "auth", "rate_limit", "chrome", ...), `message` is what the User reads (what happened, what to do),
`status` is the HTTP status if there was one. The Runner turns any other exception into a generic line; these say something useful.
"""

from __future__ import annotations


class Failure(Exception):
    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind, self.message, self.status = kind, message, status
