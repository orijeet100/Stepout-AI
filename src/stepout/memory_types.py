"""The words of Memory, with no behaviour: what an entry is, what a Run is handed, what a store must do.

(ADR 0003, 0016.) Memory is what the Assistant knows about the User going into a Task. It is not the Ledger (what happened; the model never sees it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Protocol, Sequence

Kind = Literal["persona", "fact", "history"]


@dataclass(frozen=True)
class Entry:
    id: str  # what /forget takes: "p-3f9a1c" (persona), "f-..." (learned fact), "h-..." (an earlier task)
    kind: Kind
    text: str
    at: datetime | None = None
    conversation_id: str | None = None  # the chat it came from: deleting that chat removes it
    run_id: str | None = None
    source: str = ""  # where it came from, in words the User can check ("you said it on 2026-10-12", "a task outcome")


@dataclass(frozen=True)
class Recollection:
    """What a Run is handed at its start. `text` is empty when there is nothing to hand over."""

    text: str = ""
    ids: tuple[str, ...] = ()
    skipped: str = ""  # why it is partial, when it is (a Persona longer than its share)

    @property
    def chars(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class RunRecord:
    """What a finished Run leaves in History. Written by code from the Run itself; `did` is capability names and hosts only, never a model's words."""

    request: str  # the User's own message
    outcome: str  # done | failed | cancelled
    did: str
    tainted: bool  # the Run held file contents: only the request and the outcome are kept
    conversation_id: str
    run_id: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LearnedStore(Protocol):
    """Where learned facts and History live (the seam of ADR 0003: plain files, or Mem0). Persona is never in here: it is a file the User owns."""

    async def search(self, query: str) -> list[Entry]: ...
    async def add(self, entry: Entry) -> Entry: ...
    async def entries(self) -> list[Entry]: ...
    async def delete(self, entry_id: str) -> Entry | None: ...
    async def delete_chat(self, conversation_id: str) -> int: ...


class Memory(Protocol):
    enabled: bool  # False for the off switch: nothing is recalled or written, and the commands say so

    async def recall(self, request: str) -> Recollection: ...
    async def record_run(self, record: RunRecord) -> None: ...
    async def learn(self, facts: Sequence[str], *, conversation_id: str, message_at: datetime) -> list[Entry]: ...
    async def remember(self, text: str) -> Entry: ...
    async def entries(self) -> list[Entry]: ...
    async def forget(self, entry_id: str) -> Entry | None: ...
    async def forget_chat(self, conversation_id: str) -> int: ...
    def take_cost(self) -> float: ...  # dollars spent (estimated) on embeddings since the last call
