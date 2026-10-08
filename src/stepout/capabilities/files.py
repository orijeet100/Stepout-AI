"""files: look at the User's disk: names, sizes, dates, counts. Never contents. The hand is `stepout.files.Files` (grants, block list)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from stepout.capabilities.base import TEXT_CHARS, Capability, RunContext, tool_schema


class FilesAction(BaseModel):
    """Look at the User's disk: names, sizes, dates, counts. Never contents."""

    kind: Literal["files"] = "files"
    op: Literal["list", "find", "count"]
    path: str
    pattern: str | None = None


class Files(Capability):
    name = "files"
    blurb = "Lists folders, counts files by type and finds files by name on the User's disk, inside their grants; never opens a file or reads its contents."
    tool = tool_schema(
        "files",
        "Look at the user's disk: names, sizes, dates and counts only, never file contents. op 'list' shows one folder; "
        "'count' totals a whole folder tree by file extension; 'find' searches a folder tree for names containing the pattern "
        "(or matching a * glob; several quoted or comma-separated terms match any of them), newest first. Paths are Windows paths such as D:\\Documents.",
        required=["op", "path"],
        op={"type": "string", "enum": ["list", "count", "find"]},
        path={"type": "string"},
        pattern={"type": "string"},
    )
    action = FilesAction

    def summary(self, action: FilesAction) -> str:
        return f"files {action.op} {action.path}" + (f" {action.pattern}" if action.pattern else "")

    def repeat_guard(self, action: FilesAction) -> bool:
        return True

    async def run(self, action: FilesAction, ctx: RunContext) -> str:
        result = await ctx.hands["files"].run(action.op, action.path, action.pattern, ctx.cancelled)
        return f"files {action.op} {action.path}:\n{result[:TEXT_CHARS]}"
