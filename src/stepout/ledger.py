"""Ledger: append-only record of everything that happened. Not Memory; the model never sees it."""

from __future__ import annotations

import json

from stepout.domain import Event
from stepout.store import Store


class Ledger:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, event: Event) -> None:
        self._store.execute(
            "INSERT INTO events (id, task_id, run_id, kind, data, cost_usd, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.task_id,
                event.run_id,
                event.kind,
                json.dumps(event.data),
                event.cost_usd,
                event.at.isoformat(),
            ),
        )

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
                kind=r["kind"],
                data=json.loads(r["data"]),
                cost_usd=r["cost_usd"],
                at=r["at"],
            )
            for r in rows
        ]

    def cost_since(self, since_iso: str) -> float:
        rows = self._store.query("SELECT COALESCE(SUM(cost_usd), 0) AS total FROM events WHERE at >= ?", (since_iso,))
        return rows[0]["total"]
