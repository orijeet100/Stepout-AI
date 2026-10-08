"""The capability registry. `ALL` is the one place a capability is registered: a new capability is a new file plus one line here.

Read `ALL` through these functions (not `from ... import ALL`), so a capability added at run time, as the tests do, is seen.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from stepout.capabilities.base import Capability, RunContext
from stepout.capabilities.browse import Browse
from stepout.capabilities.fetch import Fetch
from stepout.capabilities.files import Files
from stepout.capabilities.web_search import WebSearch

ALL: list[Capability] = [WebSearch(), Fetch(), Files(), Browse()]


def get(name: str) -> Capability | None:
    return next((c for c in ALL if c.name == name), None)


def blurbs() -> dict[str, str]:
    return {c.name: c.blurb for c in ALL}


def action_types() -> tuple[type[BaseModel], ...]:
    return tuple(c.action for c in ALL if c.action is not None)


def parse(name: str, args: dict[str, Any]) -> BaseModel | None:
    """A model's tool call as the capability's Action; None if `name` is not a capability the Runner runs."""
    cap = get(name)
    return cap.action(**args) if cap is not None and cap.action is not None else None
