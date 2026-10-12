"""The one SQL module. SQLite now; Postgres when a second machine or many users write (ADR 0006)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        # PRAGMA user_version = how many migrations have run, so ALTERs apply exactly once.
        applied = self._conn.execute("PRAGMA user_version").fetchone()[0]
        migrations = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        if 0 < applied < len(migrations):  # a database with data in it, about to change shape: keep what it was (the copy is named for the first version it lacks)
            backup = sqlite3.connect(path.with_name(f"{path.name}.bak-before-v{applied + 1}"))
            self._conn.backup(backup)
            backup.close()
        for n, migration in enumerate(migrations, start=1):
            if n > applied:
                self._conn.executescript(migration.read_text())
                self._conn.execute(f"PRAGMA user_version = {n}")
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def atomic(self, statements: list[tuple[str, tuple]]) -> None:
        """Run the statements as one unit: all of them or, if one fails, none."""
        try:
            for sql, params in statements:
                self._conn.execute(sql, params)
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()
