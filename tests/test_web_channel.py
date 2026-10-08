"""The web channel speaks UI contract v1: frames over /ws, read-only JSON over /api, and the contract's security rules.

Most tests run the real channel over a fake HistoryReader backed by web/fixtures (the plan's design); the last one runs
the real app loop (Intake, Runner, Ledger, Store, history.py) behind it with a scripted model, so nothing but the
model is fake.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pytest
from pydantic import TypeAdapter

from stepout.app import SavedChannel, run
from stepout.channels.web import StoreHistory, WebChannel, _valid_id
from stepout.contract import ConversationDetail, ConversationSummary, MessageFrame, NewConversation, RunSummary, ServerFrame, TraceFrame
from stepout.domain import DEFAULT_CONVERSATION, Event, Reply
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.runner import Runner
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel
from tests.test_history import NoFetcher
from tests.test_runner import FakeBrowser, browse, plan, say

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"
HEX = "0123456789abcdef0123456789abcdef"
SERVER_FRAMES = TypeAdapter(list[ServerFrame])


class FixtureHistory:
    """A HistoryReader over the UI lane's fixtures: what the page was built against."""

    def __init__(self) -> None:
        self.chats = {}
        for path in sorted(FIXTURES.glob("*.json")):
            frames = json.loads(path.read_text(encoding="utf-8"))
            messages = [MessageFrame.model_validate(f) for f in frames if f["type"] == "message"]
            events = [TraceFrame.model_validate(f) for f in frames if f["type"] == "trace"]
            self.chats[messages[0].conversation_id] = (messages, events)

    def list_conversations(self):
        return sorted(
            (ConversationSummary(id=cid, title=m[0].text[:60], updated_at=m[-1].at, preview=m[-1].text[:80], state="idle") for cid, (m, _) in self.chats.items()),
            key=lambda c: c.updated_at, reverse=True,
        )

    def get_conversation(self, conversation_id):
        if conversation_id not in self.chats:
            return None
        messages, events = self.chats[conversation_id]
        runs = []
        for rid in dict.fromkeys(e.run_id for e in events):
            own = [e for e in events if e.run_id == rid]
            state = "stopped" if any(e.kind == "stop" for e in own) else "done"
            runs.append(RunSummary(run_id=rid, request=messages[0].text, state=state, cost_usd=sum(e.cost_usd for e in own), cap_usd=1.0, steps=sum(e.kind == "step" for e in own), started_at=own[0].at, ended_at=own[-1].at))
        return ConversationDetail(id=conversation_id, title=messages[0].text[:60], messages=messages, runs=runs)

    def run_events(self, run_id):
        return [e for _, events in self.chats.values() for e in events if e.run_id == run_id]


@pytest.fixture
async def served(tmp_path):
    channel = WebChannel(port=0, shots=tmp_path, history=FixtureHistory())
    port = await channel.start()
    yield channel, f"http://127.0.0.1:{port}"
    await channel.stop()


@pytest.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        yield session


async def connect(client, base):
    ws = await client.ws_connect(f"{base}/ws", origin=base)
    assert (await ws.receive_json()) == {"type": "hello", "v": 1}
    status = await ws.receive_json()
    assert status["type"] == "status"
    return ws


async def frames(ws, n, timeout=3):
    return [await asyncio.wait_for(ws.receive_json(), timeout) for _ in range(n)]


def a_chat_id():
    return next(iter(FixtureHistory().chats))


# ---- WebSocket ----------------------------------------------------------------------------------------------------


async def test_hello_then_an_idle_status_on_connect(served, client):
    _, base = served
    async with client.ws_connect(f"{base}/ws", origin=base) as ws:
        hello, status = await frames(ws, 2)
        assert hello == {"type": "hello", "v": 1}
        assert status["state"] == "idle" and status["active"] is None and status["queued"] == []
        SERVER_FRAMES.validate_python([hello, status])


async def test_a_sent_message_is_echoed_and_handed_to_the_app_loop_with_its_chat(served, client):
    channel, base = served
    cid = a_chat_id()
    ws = await connect(client, base)
    await ws.send_json({"type": "send", "conversation_id": cid, "text": "  hello  "})
    (echo,) = await frames(ws, 1)
    assert (echo["type"], echo["role"], echo["text"], echo["conversation_id"], echo["run_id"], echo["cost_usd"]) == ("message", "user", "hello", cid, None, None)
    message = await asyncio.wait_for(anext(channel.messages()), 2)
    assert (message.text, message.conversation_id, message.id) == ("hello", cid, echo["id"])
    (status,) = await frames(ws, 1)
    assert status["state"] == "running" and status["queued"] == []  # picked up at once: running, not queued
    await ws.close()


async def test_trace_and_reply_frames_are_contract_frames_and_the_status_follows_the_run(served, client):
    channel, base = served
    cid = a_chat_id()
    run_id = next(iter(FixtureHistory().chats[cid][1])).run_id  # a run the fake history knows: its cap is 1.0
    ws = await connect(client, base)
    await ws.send_json({"type": "send", "conversation_id": cid, "text": "go"})
    await frames(ws, 1)  # the echo
    await asyncio.wait_for(anext(channel.messages()), 2)
    assert (await frames(ws, 1))[0]["state"] == "running"

    await channel.trace(Event(kind="step", role="browser", run_id=run_id, conversation_id=cid, parent="p" * 32, data={"summary": "browse open https://x.example", "verdict": "allow"}, cost_usd=0.01))
    status, step = await frames(ws, 2)
    assert status["state"] == "running" and status["active"] == {"conversation_id": cid, "run_id": run_id, "cap_usd": 1.0}  # first event: now we know the Run
    assert (step["type"], step["kind"], step["parent"], step["run_id"], step["cost_usd"]) == ("trace", "step", "p" * 32, run_id, 0.01)
    await channel.trace(Event(kind="plan", role=None, run_id=run_id, conversation_id=cid, data={"summary": "plan updated", "steps": []}))
    (plan_frame,) = await frames(ws, 1)  # a second event of the same Run: no new status
    assert plan_frame["kind"] == "plan" and plan_frame["role"] is None and plan_frame["parent"] is None

    await channel.send(Reply(text="done", conversation_id=cid, run_id=run_id, cost_usd=0.02))
    reply, idle = await frames(ws, 2)
    assert (reply["role"], reply["text"], reply["run_id"], reply["cost_usd"]) == ("assistant", "done", run_id, 0.02) and idle["state"] == "idle"
    SERVER_FRAMES.validate_python([status, step, plan_frame, reply, idle])  # every frame is valid against contract.py
    for frame in (status, step, plan_frame, reply, idle):
        assert frame["at"].endswith("Z")  # ISO UTC with Z
    await ws.close()


async def test_events_without_a_chat_or_run_are_not_streamed(served, client):
    channel, base = served
    ws = await connect(client, base)
    await channel.trace(Event(kind="screening", data={}))  # no run, no chat: the page cannot place it
    await channel.trace(Event(kind="step", conversation_id=a_chat_id(), data={}))  # a chat but no run
    await channel.send(Reply(text="marker", conversation_id=a_chat_id()))
    assert (await frames(ws, 1))[0]["text"] == "marker"
    await ws.close()


async def test_messages_sent_while_a_run_is_busy_are_queued_in_order(served, client):
    channel, base = served
    a, b = list(FixtureHistory().chats)[:2]
    ws = await connect(client, base)
    await ws.send_json({"type": "send", "conversation_id": a, "text": "first"})
    await frames(ws, 1)
    gen = channel.messages()
    first = await asyncio.wait_for(anext(gen), 2)  # now busy with it
    await frames(ws, 1)  # status running
    await ws.send_json({"type": "send", "conversation_id": b, "text": "second"})
    await ws.send_json({"type": "send", "conversation_id": a, "text": "third"})
    got = await frames(ws, 4)  # echo, status, echo, status
    statuses = [f for f in got if f["type"] == "status"]
    assert statuses[0]["queued"] == [{"conversation_id": b}] and [q["conversation_id"] for q in statuses[-1]["queued"]] == [b, a]

    # the chat list says what each chat is doing
    states = {c["id"]: c["state"] for c in await (await client.get(f"{base}/api/conversations")).json()}
    assert states[a] == "running" and states[b] == "queued"
    # a queued message is not saved yet: reading the chat back still shows it
    detail = await (await client.get(f"{base}/api/conversations/{b}")).json()
    assert detail["messages"][-1]["text"] == "second" and detail["messages"][-1]["role"] == "user"

    # the app loop asks for the next message when it is done with the first: they come out in the order sent
    second, third = await asyncio.wait_for(anext(gen), 2), await asyncio.wait_for(anext(gen), 2)
    assert (first.text, second.text, third.text) == ("first", "second", "third")
    await channel.send(Reply(text="all done", conversation_id=a))
    frames_after = await frames(ws, 4)  # status for second, status for third, the reply, then idle
    assert frames_after[-1]["state"] == "idle" and frames_after[-1]["queued"] == []
    await ws.close()


async def test_a_new_chat_whose_first_message_is_queued_is_listed_and_readable(served, client):
    channel, base = served
    a = a_chat_id()
    ws = await connect(client, base)
    await ws.send_json({"type": "send", "conversation_id": a, "text": "busy"})
    await asyncio.wait_for(anext(channel.messages()), 2)
    new = (await (await client.post(f"{base}/api/conversations", json={}, headers={"Origin": base})).json())["id"]
    await ws.send_json({"type": "send", "conversation_id": new, "text": "queued in a brand new chat"})
    await asyncio.sleep(0.1)
    chats = {c["id"]: c for c in await (await client.get(f"{base}/api/conversations")).json()}
    assert chats[new]["state"] == "queued" and chats[new]["title"] == "queued in a brand new chat"
    detail = await (await client.get(f"{base}/api/conversations/{new}")).json()
    assert [m["text"] for m in detail["messages"]] == ["queued in a brand new chat"]
    await ws.close()


async def test_stop_sets_the_cancel_flag_and_is_not_a_message(served, client):
    channel, base = served
    ws = await connect(client, base)
    await ws.send_json({"type": "stop"})
    await asyncio.wait_for(channel.cancel.wait(), 2)
    channel.cancel.clear()
    await ws.send_json({"stop": True})  # a v0 page's Stop is still understood
    await asyncio.wait_for(channel.cancel.wait(), 2)
    assert not channel._waiting
    await ws.close()


async def test_a_v0_page_can_still_send_into_the_default_chat(served, client):
    channel, base = served
    ws = await connect(client, base)
    await ws.send_json({"text": "from an old page"})
    echo = (await frames(ws, 1))[0]
    assert (echo["conversation_id"], echo["text"]) == (DEFAULT_CONVERSATION, "from an old page")
    assert (await asyncio.wait_for(anext(channel.messages()), 2)).conversation_id == DEFAULT_CONVERSATION
    await ws.close()


async def test_bad_frames_are_ignored(served, client):
    channel, base = served
    cid = a_chat_id()
    ws = await connect(client, base)
    bad = [
        "not json", [1], {"type": "nonsense"}, {"type": "send"}, {"type": "send", "conversation_id": cid},
        {"type": "send", "conversation_id": cid, "text": "   "}, {"type": "send", "conversation_id": cid, "text": 5},
        {"type": "send", "conversation_id": cid, "text": "x", "extra": 1},  # contract.py forbids stray fields
        {"type": "send", "conversation_id": cid, "text": "x" * 20_001},
        {"type": "send", "conversation_id": "not-a-hex-id", "text": "x"}, {"type": "send", "conversation_id": "../../etc", "text": "x"},
        {"type": "send", "conversation_id": "f" * 32, "text": "x"},  # well formed but nobody made it
        {"text": "   "},
    ]
    for item in bad:
        await (ws.send_json(item) if not isinstance(item, str) else ws.send_str(item))
    await ws.send_json({"type": "send", "conversation_id": cid, "text": "real"})
    assert (await frames(ws, 1))[0]["text"] == "real"  # the first thing that came back was the good one
    assert (await asyncio.wait_for(anext(channel.messages()), 2)).text == "real"
    await ws.close()


# ---- HTTP ---------------------------------------------------------------------------------------------------------


async def test_history_is_read_from_the_reader_and_is_valid_contract_json(served, client):
    _, base = served
    chats = await (await client.get(f"{base}/api/conversations")).json()
    TypeAdapter(list[ConversationSummary]).validate_python(chats)
    assert len(chats) >= 7 and [c["updated_at"] for c in chats] == sorted((c["updated_at"] for c in chats), reverse=True)
    assert all(c["state"] == "idle" for c in chats) and chats[0]["updated_at"].endswith("Z")

    detail = await (await client.get(f"{base}/api/conversations/{chats[0]['id']}")).json()
    ConversationDetail.model_validate(detail)
    assert detail["messages"][0]["role"] == "user" and detail["messages"][0]["run_id"] is None and detail["runs"][0]["cap_usd"] == 1.0

    events = await (await client.get(f"{base}/api/runs/{detail['runs'][0]['run_id']}/events")).json()
    SERVER_FRAMES.validate_python(events)
    assert events[0]["type"] == "trace"


async def test_a_new_chat_gets_a_server_made_id_and_only_that_id_can_be_sent_to(served, client):
    channel, base = served
    r = await client.post(f"{base}/api/conversations", json={}, headers={"Origin": base})
    assert r.status == 201
    new = NewConversation.model_validate(await r.json()).id
    assert len(new) == 32 and new not in FixtureHistory().chats
    empty = await client.get(f"{base}/api/conversations/{new}")  # readable while empty
    assert empty.status == 200 and (await empty.json())["messages"] == []
    ws = await connect(client, base)
    await ws.send_json({"type": "send", "conversation_id": new, "text": "first words"})
    assert (await frames(ws, 1))[0]["conversation_id"] == new
    assert (await asyncio.wait_for(anext(channel.messages()), 2)).conversation_id == new
    await ws.close()


async def test_screenshots_are_served_only_for_files_the_assistant_wrote(served, client, tmp_path):
    _, base = served
    run = HEX
    (tmp_path / run).mkdir()
    (tmp_path / run / "1.jpg").write_bytes(b"\xff\xd8jpeg")
    (tmp_path / "secret.txt").write_text("nope")
    ok = await client.get(f"{base}/shots/{run}/1.jpg")
    assert ok.status == 200 and await ok.read() == b"\xff\xd8jpeg"
    for bad in (f"{run}/2.jpg", f"{run}/1.png", "../secret.txt", f"{run}/..%2Fsecret.txt", "nothex/1.jpg", f"{run}/1.jpg/x"):
        assert (await client.get(f"{base}/shots/{bad}")).status == 404, bad


# ---- security (docs/ui-contract.md, Security): each rule has a test -------------------------------------------------


async def test_host_must_be_127_0_0_1_or_localhost_on_our_port(served, client):
    _, base = served
    port = base.rsplit(":", 1)[1]
    for path in ("/api/conversations", f"/api/conversations/{a_chat_id()}", "/shots/" + HEX + "/1.jpg", "/"):
        for host in ("evil.example", f"evil.example:{port}", "127.0.0.1", "127.0.0.1:1", f"0.0.0.0:{port}"):
            assert (await client.get(f"{base}{path}", headers={"Host": host})).status == 403, (path, host)
        assert (await client.get(f"{base}{path}", headers={"Host": f"localhost:{port}"})).status != 403, path
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect(f"{base}/ws", origin=base, headers={"Host": "evil.example"})
    assert err.value.status == 403


async def test_a_foreign_origin_is_rejected_on_the_socket_and_the_api(served, client):
    _, base = served
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect(f"{base}/ws", origin="http://evil.example")
    assert err.value.status == 403
    assert (await client.get(f"{base}/api/conversations", headers={"Origin": "http://evil.example"})).status == 403
    assert (await client.get(f"{base}/api/conversations", headers={"Origin": base})).status == 200  # our own origin
    assert (await client.get(f"{base}/api/conversations")).status == 200  # none (a plain navigation)


async def test_a_post_needs_json_and_our_origin(served, client):
    _, base = served
    url = f"{base}/api/conversations"
    assert (await client.post(url, json={}, headers={"Origin": "http://evil.example"})).status == 403
    assert (await client.post(url, json={})).status == 403  # no Origin at all
    assert (await client.post(url, data="{}", headers={"Origin": base})).status == 415  # a form or text post
    assert (await client.post(url, data="{}", headers={"Origin": base, "Content-Type": "text/plain"})).status == 415
    assert (await client.post(url, data="a=b", headers={"Origin": base, "Content-Type": "application/x-www-form-urlencoded"})).status == 415
    assert (await client.post(url, json={}, headers={"Origin": base})).status == 201


async def test_ids_are_32_hex_and_checked_before_any_lookup(served, client):
    _, base = served
    for bad in ("nope", "..", "%2e%2e", HEX.upper(), HEX[:-1], HEX + "0", "default%00", "1;drop", "f" * 32):  # the last is well formed but unknown
        assert (await client.get(f"{base}/api/conversations/{bad}")).status == 404, bad
        assert (await client.get(f"{base}/api/runs/{bad}/events")).status == 404, bad
    assert _valid_id(DEFAULT_CONVERSATION) and not _valid_id("Default") and not _valid_id("default ")  # the one literal id allowed, for the CLI's chat


async def test_no_cors_header_is_ever_sent(served, client):
    _, base = served
    responses = [
        await client.get(f"{base}/api/conversations", headers={"Origin": base}),
        await client.post(f"{base}/api/conversations", json={}, headers={"Origin": base}),
        await client.get(f"{base}/api/conversations", headers={"Origin": "http://evil.example"}),  # refused
        await client.get(f"{base}/api/conversations/nope"),  # not found
        await client.options(f"{base}/api/conversations", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"}),  # a preflight
    ]
    for r in responses:
        assert not [h for h in r.headers if h.lower().startswith("access-control-")], r.status
    assert responses[-1].status in (403, 405)


# ---- the whole path: real app loop, real Store and history.py, scripted model -------------------------------------------


async def test_a_page_message_runs_through_the_real_app_and_reads_back_from_the_real_store(tmp_path, client):
    store = Store(tmp_path / "real.db")
    ledger = Ledger(store)
    page = ("URL: https://example.com\nTitle: Example\nText: Example Domain", "abc/1.jpg")
    model = ScriptedModel([plan("read it", role="browser"), browse("open", "https://example.com"), say("Heading: Example Domain"), say("It says Example Domain.")])
    channel = WebChannel(port=0, shots=tmp_path, history=StoreHistory(store))
    base = f"http://127.0.0.1:{await channel.start()}"
    saved = SavedChannel(channel, ledger)
    app_loop = asyncio.create_task(run(saved, Intake(model, ledger), Runner(model, NoFetcher(), ledger, saved.send, trace=channel.trace, cancel=channel.cancel, browser=FakeBrowser(page))))
    try:
        chat = (await (await client.post(f"{base}/api/conversations", json={}, headers={"Origin": base})).json())["id"]
        ws = await connect(client, base)
        await ws.send_json({"type": "send", "conversation_id": chat, "text": "read https://example.com"})

        seen = []
        async with asyncio.timeout(10):
            while not (seen and seen[-1]["type"] == "status" and seen[-1]["state"] == "idle" and any(f["type"] == "message" and f["role"] == "assistant" for f in seen)):
                seen.append(await ws.receive_json())
        SERVER_FRAMES.validate_python(seen)  # everything the real backend streamed is valid against contract.py
        assert [f["type"] for f in seen[:3]] == ["message", "status", "status"]  # echo, running (screening), running with the Run
        run_id = next(f["run_id"] for f in seen if f["type"] == "trace")
        active = [f for f in seen if f["type"] == "status" and f["active"]][0]["active"]
        assert active == {"conversation_id": chat, "run_id": run_id, "cap_usd": 1.0}
        traces = [f for f in seen if f["type"] == "trace"]
        assert [t["kind"] for t in traces if t["kind"] != "plan"] == ["step", "step", "shot", "step", "return", "step"]
        shot = next(t for t in traces if t["kind"] == "shot")["data"]
        assert shot == {"summary": "page screenshot", "shot": "abc/1.jpg", "url": "https://example.com", "title": "Example"}
        reply = next(f for f in seen if f["type"] == "message" and f["role"] == "assistant")
        assert reply["text"].startswith("It says Example Domain.") and reply["run_id"] == run_id and reply["cost_usd"] == pytest.approx(0.004)
        stored = (await (await client.get(f"{base}/api/conversations/{chat}")).json())["messages"][1]
        assert (reply["id"], reply["at"]) == (stored["id"], stored["at"])  # the live reply and the saved one are the same message: a page that reloads cannot show it twice

        # history now returns the same run: same event ids, in the order they were streamed
        listed = await (await client.get(f"{base}/api/conversations")).json()
        assert [(c["id"], c["state"]) for c in listed] == [(chat, "idle")]
        detail = await (await client.get(f"{base}/api/conversations/{chat}")).json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] and detail["runs"][0]["state"] == "done" and detail["runs"][0]["cap_usd"] == 1.0
        events = await (await client.get(f"{base}/api/runs/{run_id}/events")).json()
        assert [e["id"] for e in events] == [t["id"] for t in traces]
        await ws.close()
    finally:
        app_loop.cancel()
        await channel.stop()
