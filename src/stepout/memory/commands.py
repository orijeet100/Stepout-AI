"""The slash commands: what the User can say that is not a Task. They run in the app loop, so every Channel has them, and they cost nothing.

/remember <fact>   keep a line in Persona (the file the User owns)
/memory            list everything Memory holds, with an id for each
/forget <id>       remove one entry; an id may be shortened to anything that matches only one
"""

from __future__ import annotations

from stepout.memory.types import Entry, Memory

_KIND = {"persona": "Persona (a line you wrote)", "fact": "Learned from what you said", "history": "Earlier tasks"}
_OFF = "Memory is off (STEPOUT_MEMORY=off), so there is nothing to keep or list."
_SHOWN = 60  # entries listed at most


def _listing(entries: list[Entry]) -> str:
    if not entries:
        return "Memory is empty. `/remember <fact>` adds a line to your Persona."
    lines = []
    for kind, title in _KIND.items():
        group = [e for e in entries if e.kind == kind]
        if group:
            lines += ["", f"**{title}**"]
            lines += [f"- `{e.id}` {e.text} ({e.source})" if e.source else f"- `{e.id}` {e.text}" for e in group]
    shown = len(lines)
    body = lines if shown <= _SHOWN + 8 else lines[: _SHOWN + 8] + [f"... and {shown - _SHOWN - 8} more lines"]
    return "What I keep about you:" + "\n".join(["", *body]) + "\n\n`/forget <id>` removes one."


async def handle(name: str, args: str, memory: Memory) -> str | None:
    """The reply to a command, or None if it is not one of ours (the caller says "Unknown command")."""
    args = args.strip()
    match name:
        case "remember":
            if not memory.enabled:
                return _OFF
            if not args:
                return "Say what to remember: `/remember I keep my CV in D:\\Career`."
            entry = await memory.remember(args)
            return f"Kept in your Persona as `{entry.id}`: {entry.text}"
        case "memory":
            return _OFF if not memory.enabled else _listing(await memory.entries())
        case "forget":
            if not memory.enabled:
                return _OFF
            if not args:
                return "Say which one: `/forget <id>` (`/memory` lists them)."
            matches = [e for e in await memory.entries() if e.id == args or e.id.startswith(args)]
            exact = [e for e in matches if e.id == args]
            matches = exact or matches
            if not matches:
                return f"Nothing is kept under `{args}`. `/memory` lists what is."
            if len(matches) > 1:
                return "More than one matches; use more of the id:\n" + "\n".join(f"- `{e.id}` {e.text}" for e in matches[:10])
            gone = await memory.forget(matches[0].id)
            return f"Forgot `{gone.id}`: {gone.text}" if gone is not None else f"`{matches[0].id}` was already gone."
    return None
