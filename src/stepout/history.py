"""Read saved chats and runs back. Read-only. Returns the wire types of contract.py; the web channel serves them as JSON.

`state` can only be what the database knows: idle or running. "queued" is the live Runner's to add.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from stepout.contract import ConversationDetail, ConversationSummary, MessageFrame, RunSummary, TraceFrame
from stepout.domain import Exchange
from stepout.store import Store

_RUN_STATE = {None: "running", "done": "done", "cancelled": "stopped"}  # any other ended outcome reads as "failed"
_PREVIEW_CHARS = 80
_COST_FOOTER = re.compile(r"\n\n\(cost: \$[\d.]+\)\s*$")  # replies saved before the footer was dropped still carry it


def list_conversations(store: Store) -> list[ConversationSummary]:
    """Newest first. `preview` is the first line of the chat's last message."""
    chats = []
    for c in store.query("SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"):
        last = store.query("SELECT data FROM events WHERE conversation_id = ? AND kind = 'message' ORDER BY at DESC, rowid DESC LIMIT 1", (c["id"],))
        text = json.loads(last[0]["data"])["text"] if last else ""
        running = store.query(
            "SELECT 1 FROM runs JOIN tasks ON tasks.id = runs.task_id WHERE tasks.conversation_id = ? AND runs.ended_at IS NULL LIMIT 1", (c["id"],)
        )
        preview = (text.strip().splitlines() or [""])[0][:_PREVIEW_CHARS]
        chats.append(ConversationSummary(id=c["id"], title=c["title"], updated_at=c["updated_at"], preview=preview, state="running" if running else "idle"))
    return chats


def get_conversation(store: Store, conversation_id: str) -> ConversationDetail | None:
    """The chat's messages in order and its Runs, oldest first; None if there is no such chat."""
    chat = store.query("SELECT id, title FROM conversations WHERE id = ?", (conversation_id,))
    if not chat:
        return None
    messages = [
        MessageFrame(id=r["id"], conversation_id=conversation_id, at=r["at"], **json.loads(r["data"]))
        for r in store.query("SELECT id, data, at FROM events WHERE conversation_id = ? AND kind = 'message' ORDER BY at, rowid", (conversation_id,))
    ]
    runs = [
        RunSummary(
            run_id=r["id"], request=r["request"], state=_RUN_STATE.get(r["outcome"], "failed"), cost_usd=r["cost_usd"], cap_usd=r["cap_usd"],
            steps=r["steps"], started_at=r["started_at"], ended_at=r["ended_at"],
            input_tokens=r["input_tokens"] or 0, output_tokens=r["output_tokens"] or 0, retries=r["retries"] or 0,
        )
        for r in store.query(
            "SELECT runs.id, tasks.request, runs.outcome, runs.cost_usd, runs.cap_usd, runs.started_at, runs.ended_at, "
            "runs.input_tokens, runs.output_tokens, runs.retries, "
            "(SELECT COUNT(*) FROM events WHERE events.run_id = runs.id AND events.kind = 'step') AS steps "
            "FROM runs JOIN tasks ON tasks.id = runs.task_id WHERE tasks.conversation_id = ? ORDER BY runs.started_at",
            (conversation_id,),
        )
    ]
    return ConversationDetail(id=chat[0]["id"], title=chat[0]["title"], messages=messages, runs=runs)


def run_events(store: Store, run_id: str) -> list[TraceFrame]:
    """Exactly what was streamed live for the Run, in order. (Events from before chats existed belong to none and are left out.)"""
    return [
        TraceFrame(
            id=r["id"], conversation_id=r["conversation_id"], run_id=run_id, parent=r["parent"], kind=r["kind"],
            role=r["role"], data=json.loads(r["data"]), cost_usd=r["cost_usd"], at=r["at"],
        )
        for r in store.query("SELECT * FROM events WHERE run_id = ? AND conversation_id IS NOT NULL ORDER BY at, rowid", (run_id,))
    ]


def did_line(events, *, hosts_only: bool = False) -> str:
    """What the specialists' hands did in a Run, from its step events (anything with `.kind`, `.role` and `.data`): "browse open luma.com/discover; fetch luma.com/tech".
    `hosts_only`: for Memory, which keeps it across chats. Only the kind of action and, for a web page, its host: no query, no path, no file name, nothing a page or a
    file could have worded."""
    done: list[str] = []
    for e in events:
        if e.kind == "step" and e.role != "orchestrator" and e.data.get("verdict") == "allow" and not e.data.get("repeat") and e.data["action"]["kind"] != "answer":
            if hosts_only:
                action = e.data["action"]
                host = re.sub(r"[^A-Za-z0-9.:-]", "", urlparse(str(action.get("url") or "")).netloc)[:80]
                line = f"{action['kind']} {host}".strip()
            else:
                line = re.sub(r"https?://", "", e.data["summary"])
            if line not in done:
                done.append(line)
    return "; ".join(done)[:200]


def _did(store: Store, run_id: str) -> str:
    return did_line(run_events(store, run_id))


def exchanges(store: Store, conversation_id: str, last: int = 5) -> list[Exchange]:
    """The chat's answered messages, in the order they were answered, numbered from 1; only the newest `last` are built (the numbers stay the
    chat's own). A Run's reply answers its Run's Request; a reply with no Run (Screening's chat answer, a decline, an error) answers the message
    just before it, so small talk is context for what follows too. A Run that never replied (a crash) is not an Exchange."""
    chat = get_conversation(store, conversation_id)
    if chat is None:
        return []
    runs = {r.run_id: r for r in chat.runs}
    tainted = {
        r["id"] for r in store.query("SELECT runs.id FROM runs JOIN tasks ON tasks.id = runs.task_id WHERE tasks.conversation_id = ? AND runs.tainted IS NOT NULL", (conversation_id,))
    }
    answered: list[tuple[str, str, str]] = []  # (request, reply, run id or "")
    asked: str | None = None  # the newest message a reply with no Run has not answered yet
    for m in chat.messages:
        if m.role == "user":
            asked = m.text
        elif m.run_id in runs:
            answered.append((runs[m.run_id].request, m.text, m.run_id))
        elif asked is not None:
            answered.append((asked, m.text, ""))
            asked = None
    return [
        Exchange(id=n, request=q, reply=_COST_FOOTER.sub("", a), did=_did(store, rid) if rid else "", tainted=rid in tainted, run_id=rid)
        for n, (q, a, rid) in enumerate(answered, start=1)
        if n > len(answered) - last
    ]


def _like(text: str) -> str:
    """A LIKE pattern for "contains `text`", with `!` as the escape character so a % or _ the User typed means itself."""
    return "%" + text.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def search_conversations(store: Store, text: str) -> list[ConversationSummary]:
    """The chats whose title or any message contains `text` (case-insensitive), newest first. Message text only: a Run's trace is not searched.
    ponytail: a substring scan, fine for a few thousand messages; full-text indexing only if this is measured slow."""
    pattern = _like(text.strip())
    hits = {
        r["conversation_id"]
        for r in store.query(
            "SELECT DISTINCT conversation_id FROM events WHERE kind = 'message' AND conversation_id IS NOT NULL "
            "AND json_extract(data, '$.text') LIKE ? ESCAPE '!'",
            (pattern,),
        )
    }
    hits |= {r["id"] for r in store.query("SELECT id FROM conversations WHERE title LIKE ? ESCAPE '!'", (pattern,))}
    return [c for c in list_conversations(store) if c.id in hits]


def export_markdown(store: Store, conversation_id: str) -> str | None:
    """One chat as Markdown: its title, then each message in order. None if there is no such chat. No trace data."""
    chat = get_conversation(store, conversation_id)
    if chat is None:
        return None
    lines = [f"# {chat.title}", ""]
    for m in chat.messages:
        lines += [f"**{'You' if m.role == 'user' else 'Assistant'}** ({m.at:%Y-%m-%d %H:%M})", "", _COST_FOOTER.sub("", m.text), ""]
    return "\n".join(lines)
