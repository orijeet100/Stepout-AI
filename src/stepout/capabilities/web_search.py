"""web_search: look something up on the web. The hand is `stepout.access.search.Searcher` (one cheap model call that uses the provider's own search tool)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from stepout.capabilities.base import TEXT_CHARS, Capability, RunContext, tool_from

MAX_SEARCHES = 3  # per Run


class WebSearchAction(BaseModel):
    kind: Literal["web_search"] = "web_search"
    query: str


class WebSearch(Capability):
    name = "web_search"
    blurb = "Searches the web for current facts, a few searches per run; answers carry their source links."
    tool = tool_from(
        WebSearchAction,
        f"Search the web for current information. Returns a short summary with source links. At most {MAX_SEARCHES} searches per task.",
    )
    action = WebSearchAction
    reaches_web = True  # the Gate closes it once a file has been read, like fetch and browse

    def summary(self, action: WebSearchAction) -> str:
        return f"web_search {action.query}"

    def repeat_guard(self, action: WebSearchAction) -> bool:
        return True

    async def run(self, action: WebSearchAction, ctx: RunContext) -> str:
        used = ctx.state.scratch.get(self.name, 0)
        if used >= MAX_SEARCHES:
            return f"No searches left for this task ({MAX_SEARCHES} used). Work from what you have."
        ctx.state.scratch[self.name] = used + 1
        text, cost = await ctx.hands[self.name].search(action.query)
        ctx.charge(cost)  # the search was a model call of its own
        return f"web_search {action.query}:\n{text[:TEXT_CHARS]}"
