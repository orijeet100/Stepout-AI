"""Managing saved chats over the real channel, Store and Ledger: rename, search, export, and delete as a purge."""

import aiohttp
import pytest

from stepout.channels.web import StoreHistory, WebChannel
from stepout.chats import ChatKeeper
from stepout.domain import Event, Message, Outcome, Task
from stepout.ledger import Ledger
from stepout.store import Store

A, B = "a" * 32, "b" * 32


def save_chat(ledger: Ledger, chat: str, run: str, request: str, reply: str, trace: str = "internal trace words") -> None:
    task = Task(user_id="u", request=request, conversation_id=chat)
    ledger.save_message(chat, "user", request)
    ledger.start_run(task, run, 1.0)
    ledger.record(Event(kind="step", task_id=task.id, run_id=run, conversation_id=chat, role="orchestrator", data={"summary": trace}))
    ledger.save_message(chat, "assistant", reply, run_id=run, cost_usd=0.01)
    ledger.end_run(run, Outcome.DONE, 0.01, "")


@pytest.fixture
async def world(tmp_path):
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    shots = tmp_path / "runs"
    shots.mkdir()
    cleaned = []

    async def hook(chat, run_ids):
        cleaned.append((chat, run_ids))

    keeper = ChatKeeper(ledger, shots, [hook])
    channel = WebChannel(port=0, shots=shots, history=StoreHistory(store), keeper=keeper)
    port = await channel.start()
    base = f"http://127.0.0.1:{port}"
    async with aiohttp.ClientSession(headers={"Origin": base}) as session:
        yield type("World", (), {"store": store, "ledger": ledger, "shots": shots, "channel": channel, "http": session, "base": base, "cleaned": cleaned})
    await channel.stop()


async def chat_ids(w, query=""):
    async with w.http.get(f"{w.base}/api/conversations{query}") as r:
        return [c["id"] for c in await r.json()]


async def test_a_chat_is_renamed_and_the_list_shows_it(world):
    save_chat(world.ledger, A, "r1", "weather in oslo", "Cold.")
    async with world.http.patch(f"{world.base}/api/conversations/{A}", json={"title": "  Oslo weather "}) as r:
        assert r.status == 200 and (await r.json()) == {"id": A, "title": "Oslo weather"}
    async with world.http.get(f"{world.base}/api/conversations") as r:
        assert [c["title"] for c in await r.json()] == ["Oslo weather"]


async def test_a_bad_title_or_an_unknown_chat_is_refused(world):
    save_chat(world.ledger, A, "r1", "q", "a")
    for body in ({"title": ""}, {"title": "x" * 121}, {"nope": 1}):
        async with world.http.patch(f"{world.base}/api/conversations/{A}", json=body) as r:
            assert r.status == 422
    async with world.http.patch(f"{world.base}/api/conversations/{B}", json={"title": "x"}) as r:
        assert r.status == 404


async def test_deleting_a_chat_removes_everything_about_it_and_nothing_else(world):
    save_chat(world.ledger, A, "run-a", "first chat", "reply one")
    save_chat(world.ledger, B, "run-b", "second chat", "reply two")
    (world.shots / "run-a").mkdir()
    (world.shots / "run-a" / "1.jpg").write_bytes(b"jpg")
    (world.shots / "run-b").mkdir()

    async with world.http.delete(f"{world.base}/api/conversations/{A}") as r:
        assert r.status == 204

    assert await chat_ids(world) == [B]
    assert not (world.shots / "run-a").exists() and (world.shots / "run-b").exists()
    left = {t: world.store.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in ("events", "runs", "tasks", "conversations")}
    assert left == {"events": 3, "runs": 1, "tasks": 1, "conversations": 1}  # chat B's message, trace step, reply; its Run, Task and chat
    assert world.cleaned == [(A, ["run-a"])]  # Memory and Capture clean up through this
    async with world.http.delete(f"{world.base}/api/conversations/{A}") as r:
        assert r.status == 404


async def test_a_chat_with_a_run_in_progress_or_waiting_cannot_be_deleted(world):
    save_chat(world.ledger, A, "r1", "q", "a")
    world.channel._waiting.append(Message(user_id="local", text="another", conversation_id=A))  # queued behind a Run
    async with world.http.delete(f"{world.base}/api/conversations/{A}") as r:
        assert r.status == 409
    assert await chat_ids(world) == [A]


async def test_a_failing_cleanup_does_not_undo_the_delete(tmp_path):
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    save_chat(ledger, A, "r1", "q", "a")

    async def broken(chat, run_ids):
        raise OSError("disk says no")

    assert await ChatKeeper(ledger, tmp_path, [broken]).delete(A) is True
    assert store.query("SELECT COUNT(*) AS n FROM conversations")[0]["n"] == 0


async def test_search_finds_a_message_in_any_chat_and_ignores_the_trace(world):
    save_chat(world.ledger, A, "r1", "plan a trip to Lisbon", "Here is a plan.", trace="secret-trace-word")
    save_chat(world.ledger, B, "r2", "count my pdfs", "You have 3.")
    assert await chat_ids(world, "?q=lisbon") == [A]  # case-insensitive
    assert await chat_ids(world, "?q=3.") == [B]
    assert await chat_ids(world, "?q=secret-trace-word") == []  # a Run's trace is not searched
    assert await chat_ids(world, "?q=100%25") == []  # % means itself
    assert sorted(await chat_ids(world)) == sorted([A, B])


async def test_search_matches_a_title_too(world):
    save_chat(world.ledger, A, "r1", "weather in oslo", "Cold.")
    world.ledger.rename_conversation(A, "Holiday notes")
    assert await chat_ids(world, "?q=holiday") == [A]


async def test_a_chat_exports_as_markdown_without_trace_data(world):
    save_chat(world.ledger, A, "r1", "what is 2+3", "It is 5.", trace="secret-trace-word")
    async with world.http.get(f"{world.base}/api/conversations/{A}/export") as r:
        assert r.status == 200 and r.content_type == "text/markdown"
        assert 'filename="chat-aaaaaaaa.md"' in r.headers["Content-Disposition"]
        text = await r.text()
    assert text.startswith("# what is 2+3") and text.index("**You**") < text.index("**Assistant**") and "It is 5." in text
    assert "secret-trace-word" not in text


async def test_changing_calls_need_our_origin_and_json(world):
    save_chat(world.ledger, A, "r1", "q", "a")
    async with aiohttp.ClientSession() as bare:  # no Origin header
        async with bare.delete(f"{world.base}/api/conversations/{A}") as r:
            assert r.status == 403
        async with bare.patch(f"{world.base}/api/conversations/{A}", json={"title": "x"}) as r:
            assert r.status == 403
    async with world.http.patch(f"{world.base}/api/conversations/{A}", data="title=x") as r:
        assert r.status == 415
    assert await chat_ids(world) == [A]
