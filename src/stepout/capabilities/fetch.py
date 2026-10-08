"""fetch: read one public page by URL. The hand is `stepout.fetch.Fetcher` (it polices every address)."""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel

from stepout.capabilities.base import TEXT_CHARS, Capability, RunContext, tool_schema
from stepout.fetch import BlockedUrl


class FetchAction(BaseModel):
    kind: Literal["fetch"] = "fetch"
    url: str


class Fetch(Capability):
    name = "fetch"
    blurb = "Reads one public web page whose address is known, as text; no logins, scripts or forms."
    tool = tool_schema("fetch", "Read one web page whose URL you already know. Returns its text.", url={"type": "string"})
    action = FetchAction
    reaches_web = True

    def summary(self, action: FetchAction) -> str:
        return f"fetch {action.url}"

    def repeat_guard(self, action: FetchAction) -> bool:
        return True

    async def run(self, action: FetchAction, ctx: RunContext) -> str:
        try:
            page = await ctx.hands["fetch"].get(action.url)
        except (BlockedUrl, httpx.HTTPError) as exc:
            return f"Fetching {action.url} failed: {exc}"
        return f"Fetched {action.url}:\n{page.text[:TEXT_CHARS]}"
