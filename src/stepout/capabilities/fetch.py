"""fetch: read one public page by URL. The hand is `stepout.access.fetch.Fetcher` (it polices every address)."""

from __future__ import annotations

import asyncio
from typing import Literal

import httpx
from pydantic import BaseModel

from stepout.backoff import RETRY_AFTER_CEILING_S, TOOL_ATTEMPTS, TOOL_BASE_S, TOOL_CAP_S, wait
from stepout.capabilities.base import TEXT_CHARS, Capability, RunContext, tool_from
from stepout.access.fetch import BlockedUrl

_RETRY_STATUS = (429, 500, 502, 503, 504)


class FetchAction(BaseModel):
    kind: Literal["fetch"] = "fetch"
    url: str


class Fetch(Capability):
    name = "fetch"
    blurb = "Reads one public web page whose address is known, as text; no logins, scripts or forms."
    tool = tool_from(FetchAction, "Read one web page whose URL you already know. Returns its text.")
    action = FetchAction
    reaches_web = True

    def summary(self, action: FetchAction) -> str:
        return f"fetch {action.url}"

    def repeat_guard(self, action: FetchAction) -> bool:
        return True

    async def run(self, action: FetchAction, ctx: RunContext) -> str:
        for attempt in range(1, TOOL_ATTEMPTS + 1):
            try:
                page = await ctx.hands["fetch"].get(action.url)
                return f"Fetched {action.url}:\n{page.text[:TEXT_CHARS]}"
            except (BlockedUrl, httpx.HTTPError) as exc:
                delay = _transient_wait(exc, attempt) if attempt < TOOL_ATTEMPTS else None
                if delay is None:
                    return f"Fetching {action.url} failed: {exc}"
                await ctx.emit(
                    "retry", f"Fetching {action.url} failed; trying again in {delay:g} s ({attempt + 1} of {TOOL_ATTEMPTS})",
                    attempt=attempt, of=TOOL_ATTEMPTS, cause=type(exc).__name__, wait_s=delay,
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # the loop returns on its last attempt


def _transient_wait(exc: Exception, attempt: int) -> float | None:
    """Seconds to wait before fetching again if `exc` is the kind a second try can cure (a timeout, a dropped connection, 429 or 5xx); None if not.
    A fetch only reads, so repeating it is safe. A refused address, a 404 and a page that is too long are final."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _RETRY_STATUS:
        try:
            told = float(exc.response.headers.get("retry-after", ""))
        except ValueError:
            told = None
        if told is not None:
            return told if told <= RETRY_AFTER_CEILING_S else None
        return wait(attempt, TOOL_BASE_S, TOOL_CAP_S)
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return wait(attempt, TOOL_BASE_S, TOOL_CAP_S)
    return None
