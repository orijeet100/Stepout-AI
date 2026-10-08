"""Read saved chats and runs back. Read-only. Returns the wire types of contract.py; the web channel serves them as JSON.

`state` can only be what the database knows: idle or running. "queued" is the live Runner's to add.
"""

from __future__ import annotations

import json
import re

from stepout.contract import ConversationDetail, ConversationSummary, MessageFrame, RunSummary, TraceFrame
from stepout.domain import Exchange
from stepout.store import Store

_RUN_STATE = {None: "running", "done": "done", "cancelled": "stopped"}  # any other ended outcome reads as "failed"
_PREVIEW_CHARS = 80
_COST_FOOTER = re.compile(r"\n\n\(cost: \$[\d.]+\)\s*$")  # still on saved replies until the page reads cost_usd


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
        )
        for r in store.query(
            "SELECT runs.id, tasks.request, runs.outcome, runs.cost_usd, runs.cap_usd, runs.started_at, runs.ended_at, "
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


def _did(store: Store, run_id: str) -> str:
    """What the specialists' hands did in a Run, from the step summaries: "browse open luma.com/discover; fetch luma.com/tech"."""
    done: list[str] = []
    for e in run_events(store, run_id):
        if e.kind == "step" and e.role != "orchestrator" and e.data.get("verdict") == "allow" and e.data["action"]["kind"] != "answer":
            line = re.sub(r"https?://", "", e.data["summary"])
            if line not in done:
                done.append(line)
    return "; ".join(done)[:200]


def exchanges(store: Store, conversation_id: str, last: int = 10) -> list[Exchange]:
    """The chat's answered Requests, oldest first, numbered from 1; only the newest `last` are built (the numbers stay the chat's own)."""
    chat = get_conversation(store, conversation_id)
    if chat is None:
        return []
    replies = {m.run_id: m.text for m in chat.messages if m.role == "assistant" and m.run_id}
    answered = [r for r in chat.runs if r.run_id in replies]  # a Run that never replied (a crash) is not an Exchange
    return [
        Exchange(id=n, request=r.request, reply=_COST_FOOTER.sub("", replies[r.run_id]), did=_did(store, r.run_id), run_id=r.run_id)
        for n, r in enumerate(answered, start=1)
        if n > len(answered) - last
    ]
