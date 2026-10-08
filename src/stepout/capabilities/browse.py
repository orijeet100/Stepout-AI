"""browse: read web pages in a headless browser, read-only. The hand is `stepout.browser.Browser` (it polices every request and redirect)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from stepout.capabilities.base import Capability, RunContext, tool_schema

_KEEP_PAGES = 2  # page views a Role keeps in full
_PAGE_HEAD = re.compile(r"URL: (.*)\nTitle: (.*)")  # how every page view starts (stepout.browser)


class BrowseAction(BaseModel):
    """Read a web page in the headless browser. Read-only: open a url, follow a numbered link, read on."""

    kind: Literal["browse"] = "browse"
    op: Literal["open", "click", "more"]
    url: str | None = None
    link: int | None = None


class Browse(Capability):
    name = "browse"
    blurb = "Reads web pages in a real headless browser, read-only: opens an address, follows a numbered link, reads on; cannot log in, type, submit or download."
    tool = tool_schema(
        "browse",
        "Read web pages in a headless browser, read-only. op 'open' loads a url; 'click' follows a numbered link from "
        "the page you last opened; 'more' shows the next part of the current page's text.",
        required=["op"],
        op={"type": "string", "enum": ["open", "click", "more"]},
        url={"type": "string"},
        link={"type": "integer", "minimum": 1},
    )
    action = BrowseAction
    reaches_web = True
    stateful = True  # `click` and `more` act on the page it is on, so after a click the same `open` is a different thing to do

    def summary(self, action: BrowseAction) -> str:
        return f"browse {action.op} {action.url or action.link or ''}".strip()

    def repeat_guard(self, action: BrowseAction) -> bool:
        return action.op == "open"  # click and more depend on where the page is, so the same call can differ

    async def run(self, action: BrowseAction, ctx: RunContext) -> str:
        view, shot = await ctx.hands["browse"].run(ctx.run_id, action.op, action.url, action.link)
        if shot:
            head = _PAGE_HEAD.match(view)  # the viewer captions the screenshot with the page's address and title
            await ctx.emit("shot", "page screenshot", shot=shot, **({"url": head[1], "title": head[2]} if head else {}))
        return f"browse {action.op}:\n{view}"

    def compact(self, notes: list[str]) -> None:
        """Page views are big and a Role re-reads its notes every step: all but the newest two shrink to their first lines."""
        pages = [i for i, n in enumerate(notes) if n.startswith("browse ")]
        for i in pages[:-_KEEP_PAGES]:
            notes[i] = "(earlier page) " + " ".join(notes[i].splitlines()[1:3])[:200]
