"""The Mem0 learned store (ADR 0016): the same seam as the plain files, with an embedding search in front of what was kept.

Mem0 runs here as a local library and nothing more: its telemetry is off, its vector store and history database sit under `<Home>/memory/` (`data/memory/` in a checkout), and every write is
`infer=False`, so Mem0's own model never runs (a guard raises if it ever tries). The extraction of facts is ours (extract.py), through the Model port.
What leaves the laptop is the text of an entry or a query, sent to the embedding provider (OpenAI `text-embedding-3-small`) to be turned into numbers.
That call is Mem0's own HTTP client and keeps its own retries, outside the policy of ADR 0015; its cost is estimated from the text's size.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from stepout.memory.types import Entry

USER = "local"  # Mem0 wants an entity to file memories under; there is one User
EMBED_PRICE_PER_M = 0.02  # $ per million tokens, text-embedding-3-small's list price: check when OpenAI's changes
EMBED_DIMS = 1536  # what that model returns; the vector store is created with it
SEARCH_K = 12  # how many the search brings back; the service keeps the best few of each kind
LIST_MAX = 2000  # entries listed at most (a year of daily use is a few thousand)


class _NoModel:
    """Mem0's own LLM must never run: extraction is ours. If a path in the library ever reaches for it, this says so loudly instead of spending money unseen."""

    def generate_response(self, *args: Any, **kwargs: Any):
        raise AssertionError("Mem0's own model was called; Memory writes with infer=False and extracts through the Model port")


def _estimate(text: str) -> float:
    return math.ceil(len(text) / 4) * EMBED_PRICE_PER_M / 1_000_000  # about four characters a token


class Mem0Store:
    def __init__(self, root: Path, *, dims: int = EMBED_DIMS, embedder: Any = None, api_key: str | None = None) -> None:
        """`embedder`: an object with `embed(text, action)`, to stand in for the provider (tests). `api_key`: OpenAI's, if not in the environment."""
        # Both are read when the library is imported: set them first, here, so it never touches the home folder or the network for telemetry.
        os.environ["MEM0_TELEMETRY"] = "False"
        os.environ.setdefault("MEM0_DIR", str(root / "mem0"))
        root.mkdir(parents=True, exist_ok=True)
        from mem0 import AsyncMemory

        key = api_key or os.environ.get("OPENAI_API_KEY") or "unused"  # the embedder needs a key to be built; the LLM below never calls with it
        self._m = AsyncMemory.from_config(
            {
                "vector_store": {"provider": "qdrant", "config": {"collection_name": "stepout", "path": str(root / "qdrant"), "embedding_model_dims": dims, "on_disk": True}},
                "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small", "api_key": key}},
                "llm": {"provider": "openai", "config": {"api_key": key}},
                "history_db_path": str(root / "mem0_history.db"),
            }
        )
        self._m.llm = _NoModel()
        if embedder is not None:
            self._m.embedding_model = embedder
        self._cost = 0.0

    def take_cost(self) -> float:
        """What the embedding calls since the last time are estimated to have cost."""
        spent, self._cost = self._cost, 0.0
        return spent

    async def add(self, entry: Entry) -> Entry:
        meta = {"kind": entry.kind, "entry_id": entry.id, "conversation_id": entry.conversation_id, "origin_run_id": entry.run_id, "source": entry.source, "at": entry.at.isoformat() if entry.at else None}
        await self._m.add([{"role": "user", "content": entry.text}], user_id=USER, metadata={k: v for k, v in meta.items() if v is not None}, infer=False)
        self._cost += _estimate(entry.text)
        return entry

    async def search(self, query: str) -> list[Entry]:
        found = await self._m.search(query, filters={"user_id": USER}, top_k=SEARCH_K)
        self._cost += _estimate(query)
        return [self._entry(item) for item in found.get("results", [])]

    async def entries(self) -> list[Entry]:
        listed = await self._m.get_all(filters={"user_id": USER}, top_k=LIST_MAX)
        return [self._entry(item) for item in listed.get("results", [])]

    async def delete(self, entry_id: str) -> Entry | None:
        for item in (await self._m.get_all(filters={"user_id": USER}, top_k=LIST_MAX)).get("results", []):
            if self._entry(item).id == entry_id:
                await self._m.delete(item["id"])
                return self._entry(item)
        return None

    async def delete_chat(self, conversation_id: str) -> int:
        gone = 0
        for item in (await self._m.get_all(filters={"user_id": USER}, top_k=LIST_MAX)).get("results", []):
            if (item.get("metadata") or {}).get("conversation_id") == conversation_id:
                await self._m.delete(item["id"])
                gone += 1
        return gone

    def close(self) -> None:
        """Release the local vector store's file lock (a second process, or a test's temp folder, needs it)."""
        try:
            self._m.vector_store.client.close()
        except Exception:
            pass

    @staticmethod
    def _entry(item: dict) -> Entry:
        meta = item.get("metadata") or {}
        at = meta.get("at")
        return Entry(
            id=meta.get("entry_id") or f"m-{str(item['id'])[:8]}",  # an entry another tool put there still has an id to forget it by
            kind=meta.get("kind", "fact"),
            text=item.get("memory", ""),
            at=datetime.fromisoformat(at) if at else None,
            conversation_id=meta.get("conversation_id"),
            run_id=meta.get("origin_run_id"),
            source=meta.get("source", ""),
        )
