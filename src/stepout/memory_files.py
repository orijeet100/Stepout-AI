"""The plain-file learned store (ADR 0003): one JSON line per entry in a file the User can open. Recall is words in common, then recency.

The baseline Mem0 is measured against. No model, no network, no embeddings.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from stepout.memory_types import Entry

_STOP = frozenset("the and for are but not you your with this that have from what when where how can will about into just like please".split())
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in _STOP}


class FileStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _load(self) -> list[Entry]:
        if not self._path.is_file():
            return []
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                out.append(Entry(**{**row, "at": datetime.fromisoformat(row["at"]) if row.get("at") else None}))
            except (ValueError, TypeError, KeyError):
                continue  # a line the User edited into something else: skipped, never fatal
        return out

    def _save(self, entries: list[Entry]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".learned-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                for e in entries:
                    f.write(json.dumps({**e.__dict__, "at": e.at.isoformat() if e.at else None}, ensure_ascii=False) + "\n")
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    async def search(self, query: str) -> list[Entry]:
        """Facts first (most in common with the query, then newest), then earlier tasks that share a word with it (the same order)."""
        wanted = words(query)

        def rank(e: Entry):
            return (-len(wanted & words(e.text)), -(e.at or _OLDEST).timestamp())

        entries = self._load()
        facts = sorted((e for e in entries if e.kind == "fact"), key=rank)
        past = sorted((e for e in entries if e.kind == "history" and wanted & words(e.text)), key=rank)
        return facts + past

    async def add(self, entry: Entry) -> Entry:
        self._save([*self._load(), entry])
        return entry

    async def entries(self) -> list[Entry]:
        return self._load()

    async def delete(self, entry_id: str) -> Entry | None:
        entries = self._load()
        gone = next((e for e in entries if e.id == entry_id), None)
        if gone is not None:
            self._save([e for e in entries if e.id != entry_id])
        return gone

    async def delete_chat(self, conversation_id: str) -> int:
        entries = self._load()
        kept = [e for e in entries if e.conversation_id != conversation_id]
        if len(kept) != len(entries):
            self._save(kept)
        return len(entries) - len(kept)
