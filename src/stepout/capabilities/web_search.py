"""web_search: the provider's own search tool. It runs on the provider's side, so it has a blurb and a schema but no Action and no `run`."""

from __future__ import annotations

from stepout.capabilities.base import Capability


class WebSearch(Capability):
    name = "web_search"
    blurb = "Searches the web for current facts, a few searches per run; answers carry their source links."
    # The basic version: 20260209+ defaults to dynamic filtering via code execution, which Haiku can't use. `max_uses` is added per request.
    tool = {"type": "web_search_20250305", "name": "web_search"}
