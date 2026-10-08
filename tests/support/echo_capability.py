"""A fake capability built from nothing but the capabilities base: the proof that one file plus one registration line is enough.

tests/test_capabilities.py checks that this file imports none of domain, model, gate, runner or roles.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from stepout.capabilities.base import Capability, RunContext, tool_schema


class EchoAction(BaseModel):
    kind: Literal["echo"] = "echo"
    text: str


class Echo(Capability):
    name = "echo"
    blurb = "Repeats a sentence back; touches nothing."
    tool = tool_schema("echo", "Repeat the text back.", text={"type": "string"})
    action = EchoAction

    def summary(self, action: EchoAction) -> str:
        return f"echo {action.text}"

    def repeat_guard(self, action: EchoAction) -> bool:
        return True

    async def run(self, action: EchoAction, ctx: RunContext) -> str:
        await ctx.emit("note", "echo ran")
        return f"echo: {action.text}"
