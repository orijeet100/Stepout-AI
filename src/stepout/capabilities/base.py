"""A Capability is one hand the Roles can hold, in one file: tool schema, Action type, executor, Gate rule, Trace line.

Subclass `Capability`, set the four class attributes, override only what differs from the defaults, and register an
instance in `capabilities.ALL`. Nothing here imports the Runner, Gate, Model or Roles: a capability reaches the world
only through `RunContext`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping

from pydantic import BaseModel

if TYPE_CHECKING:
    from stepout.domain import Verdict

TEXT_CHARS = 4000  # how much of a page, listing or Finding a Role sees


def tool_schema(name: str, description: str, required: list[str] | None = None, **props: dict) -> dict:
    """The JSON schema offered to the model; every property is required unless `required` says otherwise."""
    return {"name": name, "description": description, "input_schema": {"type": "object", "properties": props, "required": required or list(props)}}


@dataclass
class RunContext:
    """What a capability may use while one Role takes one Step."""

    run_id: str
    role: str  # the Role acting
    hands: Mapping[str, Any]  # the live hand for each capability name (Fetcher, Files, Browser, ...)
    cancelled: Callable[[], bool]  # True once the User pressed Stop
    emit: Callable[..., Awaitable[Any]]  # emit(kind, summary, **data): a Trace event under the Step that is running


class Capability:
    name: str  # the tool name the model sees; also the Action's `kind`
    blurb: str  # one line: what it can and cannot do (feeds Screening and the decline reply)
    tool: dict  # JSON schema offered to the model
    action: type[BaseModel] | None = None  # the Pydantic Action (`kind == name`); None when the provider runs it (web_search)

    async def run(self, action: Any, ctx: RunContext) -> str:
        """Do it; return the text that goes into the Role's notes."""
        raise NotImplementedError(f"{self.name} runs on the provider's side")

    def summary(self, action: Any) -> str:
        """The Trace line for this Action."""
        return action.kind

    def check(self, action: Any, ctx: RunContext | None) -> Verdict | None:
        """An extra Gate rule on top of "does this Role hold the tool". None = allow."""
        return None

    def repeat_guard(self, action: Any) -> bool:
        """True = an identical call in the same Role is not run twice (the result cannot change)."""
        return False

    def compact(self, notes: list[str]) -> None:
        """Trim this capability's old notes after it ran (a Role re-reads its notes every Step)."""
