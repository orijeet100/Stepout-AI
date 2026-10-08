"""Read saved chats back. Read-only. v0: plain dicts; the wire types of docs/ui-contract.md come with contract.py."""

from __future__ import annotations

import json

from stepout.store import Store


def list_conversations(store: Store) -> list[dict]:
    """Newest first: {id, title, updated_at}."""
    return [dict(r) for r in store.query("SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC")]


def get_conversation(store: Store, conversation_id: str) -> dict | None:
    """{id, title, messages: [{id, role, text, at}]} in order, or None if there is no such chat."""
    chat = store.query("SELECT id, title FROM conversations WHERE id = ?", (conversation_id,))
    if not chat:
        return None
    rows = store.query("SELECT id, data, at FROM events WHERE conversation_id = ? AND kind = 'message' ORDER BY at, rowid", (conversation_id,))
    messages = [{"id": r["id"], **json.loads(r["data"]), "at": r["at"]} for r in rows]
    return {**dict(chat[0]), "messages": messages}
