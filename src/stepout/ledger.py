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

    def end_run(
        self, run_id: str, outcome: Outcome, cost_usd: float, tainted: str, *,
        input_tokens: int = 0, output_tokens: int = 0, retries: int = 0, retry_wait_s: float = 0.0,
    ) -> None:
        """`tainted`: why the Run held data from the User's files ("" = it did not); what lets a later Run that builds on this one start with the web closed.
        The rest are the Run's totals (what its model calls were billed for, how often they were retried and for how long it waited)."""
        self._store.execute(
            "UPDATE runs SET outcome = ?, cost_usd = ?, ended_at = ?, tainted = ?, input_tokens = ?, output_tokens = ?, retries = ?, retry_wait_s = ? WHERE id = ?",
            (outcome.value, cost_usd, datetime.now(timezone.utc).isoformat(), tainted or None, input_tokens, output_tokens, retries, retry_wait_s, run_id),
        )

    def close_interrupted(self) -> int:
        """Close every Run that has no end as `interrupted` and say so in its Trace. Called once at start, before any Run: whatever is open then was cut off
        when the app stopped. ponytail: assumes one process per data folder; a second app on the same database would close the first one's live Run."""
        rows = self._store.query(
            "SELECT runs.id AS run_id, runs.task_id, tasks.conversation_id FROM runs JOIN tasks ON tasks.id = runs.task_id WHERE runs.ended_at IS NULL"
        )
        for r in rows:
            self._store.execute(
                "UPDATE runs SET outcome = ?, ended_at = ? WHERE id = ?", (Outcome.INTERRUPTED.value, datetime.now(timezone.utc).isoformat(), r["run_id"])
            )
            self.record(
                Event(
                    kind="error", run_id=r["run_id"], task_id=r["task_id"], conversation_id=r["conversation_id"],
                    data={"summary": "This run was cut off when the app stopped.", "cause": "interrupted", "type": "Interrupted"},
                )
            )
        return len(rows)

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
