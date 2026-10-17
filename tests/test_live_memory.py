"""Live check of the Mem0 store against the real embedding model. It costs a fraction of a cent, so the default run skips it:

    python -X utf8 -m pytest -m eval -s tests/test_live_memory.py

Needs OPENAI_API_KEY. Run it after changing the embedder or upgrading mem0ai. The offline suite (tests/test_memory_mem0.py) uses a fake embedder.
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("MEM0_DIR", tempfile.mkdtemp(prefix="stepout-mem0-live-"))
pytestmark = [pytest.mark.eval, pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")]

from stepout.memory.mem0 import Mem0Store  # noqa: E402
from stepout.memory.types import Entry  # noqa: E402


async def test_a_real_embedding_finds_the_fact_that_means_the_same_without_sharing_its_words(tmp_path):
    store = Mem0Store(tmp_path / "memory")
    try:
        now = datetime.now(timezone.utc)
        await store.add(Entry(id="f-1", kind="fact", text="Keeps their curriculum vitae in the Career folder on the D drive", at=now))
        await store.add(Entry(id="f-2", kind="fact", text="Prefers metric units and 24-hour time", at=now))
        found = await store.search("where is my resume")
        assert found and found[0].id == "f-1"
        assert 0 < store.take_cost() < 0.001  # a few hundred characters: a tiny fraction of a cent
    finally:
        store.close()
