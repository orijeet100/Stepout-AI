"""The Memory panel's three calls over the real channel: list, add a Persona line, forget one entry."""

from datetime import datetime, timezone

import aiohttp
import pytest

from stepout.channels.web import StoreHistory, WebChannel
from stepout.ledger import Ledger
from stepout.memory import MemoryService, NullMemory
from stepout.memory_files import FileStore
from stepout.persona import Persona
from stepout.store import Store

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


@pytest.fixture
async def world(tmp_path):
    memory = MemoryService(Persona(tmp_path / "persona.md"), FileStore(tmp_path / "learned.jsonl"))
    channel = WebChannel(port=0, shots=tmp_path, history=StoreHistory(Store(tmp_path / "t.db")), memory=memory)
    port = await channel.start()
    base = f"http://127.0.0.1:{port}"
    async with aiohttp.ClientSession(headers={"Origin": base}) as session:
        yield type("World", (), {"memory": memory, "http": session, "base": base, "channel": channel})
    await channel.stop()


async def test_the_panel_lists_what_memory_holds_with_where_each_came_from(world):
    await world.memory.remember("I live in Oslo")
    await world.memory.learn(["I have a dog"], conversation_id="c1", message_at=NOW)
    async with world.http.get(f"{world.base}/api/memory") as r:
        rows = await r.json()
    assert [(e["kind"], e["text"]) for e in rows] == [("persona", "I live in Oslo"), ("fact", "I have a dog")]
    assert rows[1]["source"] == "you said it on 2026-10-12" and rows[0]["id"].startswith("p-")


async def test_a_line_is_added_to_persona_and_one_entry_is_forgotten(world):
    async with world.http.post(f"{world.base}/api/memory", json={"text": "  I keep my CV in D:\\Career "}) as r:
        assert r.status == 201
        added = await r.json()
    assert added["kind"] == "persona" and added["text"] == "I keep my CV in D:\\Career"
    async with world.http.delete(f"{world.base}/api/memory/{added['id']}") as r:
        assert r.status == 204
    async with world.http.delete(f"{world.base}/api/memory/{added['id']}") as r:
        assert r.status == 404
    assert await world.memory.entries() == []


async def test_an_entry_is_edited_in_place_and_a_bad_edit_or_a_missing_origin_is_refused(world):
    await world.memory.remember("I live in Oslo")
    (fact,) = await world.memory.learn(["I have a dog"], conversation_id="c1", message_at=NOW)
    persona = (await world.memory.entries())[0]
    async with world.http.patch(f"{world.base}/api/memory/{persona.id}", json={"text": "I live in  Bergen"}) as r:
        assert r.status == 200 and (await r.json())["text"] == "I live in Bergen"
    async with world.http.patch(f"{world.base}/api/memory/{fact.id}", json={"text": "I have two dogs"}) as r:
        assert r.status == 200 and (await r.json())["kind"] == "fact"
    assert [e.text for e in await world.memory.entries()] == ["I live in Bergen", "I have two dogs"]
    async with world.http.patch(f"{world.base}/api/memory/{fact.id}", json={"text": "gone"}) as r:
        assert r.status == 404  # the old id went with the old words
    async with world.http.patch(f"{world.base}/api/memory/{persona.id}", json={"text": ""}) as r:
        assert r.status in (404, 422)
    async with aiohttp.ClientSession() as bare:
        async with bare.patch(f"{world.base}/api/memory/p-000000", json={"text": "x"}) as r:
            assert r.status == 403


async def test_a_bad_line_an_odd_id_and_a_missing_origin_are_refused(world):
    for body in ({"text": ""}, {"text": "x" * 501}, {"nope": 1}):
        async with world.http.post(f"{world.base}/api/memory", json=body) as r:
            assert r.status == 422
    async with world.http.delete(f"{world.base}/api/memory/..%2Fpersona") as r:
        assert r.status == 404
    async with aiohttp.ClientSession() as bare:
        async with bare.post(f"{world.base}/api/memory", json={"text": "x"}) as r:
            assert r.status == 403
        async with bare.delete(f"{world.base}/api/memory/p-000000") as r:
            assert r.status == 403


async def test_with_memory_off_or_absent_the_panel_is_not_there(tmp_path):
    for memory in (None, NullMemory()):
        channel = WebChannel(port=0, shots=tmp_path, history=StoreHistory(Store(tmp_path / "t.db")), memory=memory)
        port = await channel.start()
        try:
            async with aiohttp.ClientSession(headers={"Origin": f"http://127.0.0.1:{port}"}) as s:
                async with s.get(f"http://127.0.0.1:{port}/api/memory") as r:
                    assert r.status == 404
        finally:
            await channel.stop()
