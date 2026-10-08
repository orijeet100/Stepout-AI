"""Ledger: append-only record of everything that happened. Not Memory; the model never sees it."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from stepout.domain import Event, Outcome, Task
from stepout.store import Store


class Ledger:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, event: Event) -> None:
        self._store.execute(
            "INSERT INTO events (id, task_id, run_id, conversation_id, kind, role, parent, data, cost_usd, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.task_id,
                event.run_id,
                event.conversation_id,
                event.kind,
                event.role,
                event.parent,
                json.dumps(event.data),
                event.cost_usd,
                event.at.isoformat(),
            ),
        )

    def start_run(self, task: Task, run_id: str, cap_usd: float) -> None:
        """Save the Task (once) and open a Run row. A Run with no outcome yet is running."""
        self._store.execute(
            "INSERT OR IGNORE INTO tasks (id, user_id, request, conversation_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (task.id, task.user_id, task.request, task.conversation_id, task.created_at.isoformat()),
        )
        self._store.execute(
            "INSERT INTO runs (id, task_id, cap_usd, started_at) VALUES (?, ?, ?, ?)",
            (run_id, task.id, cap_usd, datetime.now(timezone.utc).isoformat()),
        )

    def end_run(self, run_id: str, outcome: Outcome, cost_usd: float) -> None:
        self._store.execute(
            "UPDATE runs SET outcome = ?, cost_usd = ?, ended_at = ? WHERE id = ?",
            (outcome.value, cost_usd, datetime.now(timezone.utc).isoformat(), run_id),
        )

    def save_message(
        self, conversation_id: str, role: str, text: str, run_id: str | None = None, cost_usd: float | None = None,
        message_id: str | None = None, at: datetime | None = None,
    ) -> None:
        """Save one chat message (role "user" or "assistant"). A chat is created by its first message and titled by it.

        `message_id` and `at` are the id and time the message already has (Message.id/at, Reply.id/at), so the saved copy is the same message the
        channel showed live. They default to fresh ones. A message that waited for a Run is dated when it was sent, not when it was saved.
        """
        extra = {k: v for k, v in (("run_id", run_id), ("cost_usd", cost_usd)) if v is not None}  # an assistant message that came from a Run
        stamp = {k: v for k, v in (("id", message_id), ("at", at)) if v is not None}
        event = Event(kind="message", conversation_id=conversation_id, data={"role": role, "text": text, **extra}, **stamp)
        when = event.at.isoformat()
        self._store.execute("INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)", (conversation_id, text[:60], when, when))
        self._store.execute("UPDATE conversations SET updated_at = MAX(updated_at, ?) WHERE id = ?", (when, conversation_id))  # never backwards
        self.record(event)

    def query(self, task_id: str | None = None) -> list[Event]:
        if task_id is not None:
            rows = self._store.query("SELECT * FROM events WHERE task_id = ? ORDER BY at", (task_id,))
        else:
            rows = self._store.query("SELECT * FROM events ORDER BY at")
        return [
            Event(
                id=r["id"],
                task_id=r["task_id"],
                run_id=r["run_id"],
                conversation_id=r["conversation_id"],
                kind=r["kind"],
                role=r["role"],
                parent=r["parent"],
                data=json.loads(r["data"]),
                cost_usd=r["cost_usd"],
                at=r["at"],
            )
            for r in rows
        ]

    def cost_since(self, since_iso: str) -> float:
        rows = self._store.query("SELECT COALESCE(SUM(cost_usd), 0) AS total FROM events WHERE at >= ?", (since_iso,))
        return rows[0]["total"]
