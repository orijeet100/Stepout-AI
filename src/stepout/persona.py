"""Persona: facts and preferences the User keeps about themselves, in one plain Markdown file they can open and edit.

One entry per bullet line (`- ...`); every other line is the User's own notes and is left alone. A line the User wrote is Pinned: nothing here
changes or removes one except the User's own `/remember` (adds a line at the end), an edit in the Memory panel (rewrites the one line) and
`/forget` (removes the one line). An entry's id is a
short hash of its text, so editing other lines never renumbers it.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from stepout.memory_types import Entry

_BULLET = "- "


def persona_id(text: str) -> str:
    return "p-" + hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:6]


class Persona:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _lines(self) -> list[str]:
        return self._path.read_text(encoding="utf-8").splitlines() if self._path.is_file() else []

    def entries(self) -> list[Entry]:
        out = []
        for line in self._lines():
            if line.startswith(_BULLET) and (text := line[len(_BULLET):].strip()):
                out.append(Entry(id=persona_id(text), kind="persona", text=text, source="you wrote it in persona.md"))
        return out

    def add(self, text: str) -> Entry:
        """Append one line. The same text twice is one entry."""
        text = " ".join(text.split())
        entry = Entry(id=persona_id(text), kind="persona", text=text, source="you wrote it in persona.md")
        if any(e.id == entry.id for e in self.entries()):
            return entry
        lines = self._lines()
        self._write([*lines, f"{_BULLET}{text}"])
        return entry

    def remove(self, entry_id: str) -> Entry | None:
        """Remove the one line with this id. Nothing else in the file changes."""
        lines = self._lines()
        for i, line in enumerate(lines):
            if line.startswith(_BULLET) and persona_id(line[len(_BULLET):]) == entry_id:
                removed = Entry(id=entry_id, kind="persona", text=line[len(_BULLET):].strip(), source="you wrote it in persona.md")
                self._write(lines[:i] + lines[i + 1 :])
                return removed
        return None

    def replace(self, entry_id: str, text: str) -> Entry | None:
        """Rewrite the one line with this id where it stands (the User's own edit). Nothing else in the file changes."""
        text = " ".join(text.split())
        lines = self._lines()
        for i, line in enumerate(lines):
            if line.startswith(_BULLET) and persona_id(line[len(_BULLET):]) == entry_id:
                self._write([*lines[:i], f"{_BULLET}{text}", *lines[i + 1 :]])
                return Entry(id=persona_id(text), kind="persona", text=text, source="you wrote it in persona.md")
        return None

    def _write(self, lines: list[str]) -> None:
        """Atomic: a crash leaves the old file or the new one, never half of one."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".persona-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
