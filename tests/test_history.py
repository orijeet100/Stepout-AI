"""Chats and Runs are saved: they survive a restart, stay apart, and read back as the wire types of contract.py."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter

from stepout import history
from stepout.app import SavedChannel, run
from stepout.contract import ConversationDetail, TraceFrame
from stepout.domain import AnswerAction, Decline, Message, Proceed, Reply, Task
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.runner import Runner
from stepout.store import _MIGRATIONS_DIR, Store
from tests.support.screeners import FixedScreener
from tests.support.scripted_model import ScriptedModel
from tests.test_runner import FakeBrowser, browse, plan, say


def test_a_0002_database_upgrades_to_the_latest_without_losing_events(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    for name in ("0001_init.sql", "0002_event_role_parent.sql"):
        conn.executescript((_MIGRATIONS_DIR / name).read_text())
    conn.execute("PRAGMA user_version = 2")
    conn.execute("INSERT INTO events (id, kind, data, at, role, run_id) VALUES ('e1', 'step', '{}', '2026-10-01T00:00:00', 'direct', 'r1')")
    conn.commit()
    conn.close()

    store = Store(path)
    assert store.query("PRAGMA user_version")[0][0] == len(list(_MIGRATIONS_DIR.glob("*.sql")))  # every migration ran
    old = Ledger(store).query()[0]
    assert (old.id, old.role, old.conversation_id) == ("e1", "direct", None)  # kept, and not in any chat
    assert history.list_conversations(store) == [] and history.run_events(store, "r1") == []


def test_saved_messages_come_back_in_order_from_a_new_store(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    ledger.save_message("a", "user", "what is the capital of France?")
    ledger.save_message("a", "assistant", "Paris")
    ledger.save_message("b", "user", "x" * 100)

    reopened = Store(tmp_path / "t.db")  # as after a restart
    chat = history.get_conversation(reopened, "a")
    assert chat.title == "what is the capital of France?"
    assert [(m.role, m.text) for m in chat.messages] == [("user", "what is the capital of France?"), ("assistant", "Paris")]
    assert [c.id for c in history.list_conversations(reopened)] == ["b", "a"]  # newest first
    assert history.list_conversations(reopened)[0].title == "x" * 60  # the first message, cut to 60
    assert history.get_conversation(reopened, "nope") is None
    assert len(history.get_conversation(reopened, "b").messages) == 1  # chats stay apart


class FakeChannel:
    def __init__(self, *messages: Message) -> None:
        self._messages, self.sent = messages, []

    async def messages(self):
        for m in self._messages:
            yield m.model_copy(update={"at": datetime.now(timezone.utc)})  # a channel stamps a message when it arrives, as the terminal does when it reads the line

    async def send(self, reply: Reply) -> None:
        self.sent.append(reply)


class NoFetcher:
    async def get(self, url):  # pragma: no cover - these requests never fetch
        raise AssertionError("fetch not expected")


def ask(cid, text):
    return Message(user_id="u", text=text, conversation_id=cid)


async def serve(tmp_path, messages, responses, screener=None, **runner_kwargs):
    """The real app loop over a fake channel and the scripted model, on a database file. The front door lets everything through unless `screener` says otherwise."""
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    model = ScriptedModel(responses)
    saved = SavedChannel(FakeChannel(*messages), ledger)
    intake = Intake(screener or FixedScreener(), ledger, lambda cid: history.exchanges(store, cid))
    await run(saved, intake, Runner(model, NoFetcher(), ledger, saved.send, **runner_kwargs))
    return Store(tmp_path / "t.db")  # as after a restart


async def test_a_conversation_through_the_app_is_saved_and_survives_a_restart(tmp_path):
    answers = [ModelResponse(action=AnswerAction(text=t), cost_usd=0.001) for t in ("Paris", "Madrid")]
    decline = Decline(reason="That means paying someone.", alternative="I can look things up.")
    screener = FixedScreener((Proceed(), 0.0), (Proceed(), 0.0), (decline, 0.0))
    reopened = await serve(tmp_path, [ask("a", "what is the capital of France?"), ask("b", "what is the capital of Spain?"), ask("a", "pay this invoice")], answers, screener)

    a, b = (history.get_conversation(reopened, c) for c in "ab")
    head = lambda m: (m.role, m.text.splitlines()[0])  # first line only: a decline joins two sentences
    assert [head(m) for m in a.messages] == [
        ("user", "what is the capital of France?"),
        ("assistant", "Paris"),
        ("user", "pay this invoice"),
        ("assistant", "That means paying someone. I can look things up."),
    ]  # a decline is saved too, and each reply went back to its own chat
    assert [head(m) for m in b.messages] == [("user", "what is the capital of Spain?"), ("assistant", "Madrid")]
    answer, declined = a.messages[1], a.messages[3]  # an answer remembers the Run that made it and what it cost; a decline had no Run, only the front door's cost
    assert (answer.run_id, answer.cost_usd) == (a.runs[0].run_id, a.runs[0].cost_usd) and answer.cost_usd > 0
    assert (declined.run_id, declined.cost_usd) == (None, 0.0)
    assert (a.title, b.title) == ("what is the capital of France?", "what is the capital of Spain?")
    assert reopened.query("SELECT COUNT(*) FROM events WHERE conversation_id IS NULL")[0][0] == 0  # every event belongs to a chat


async def test_a_browser_run_reads_back_whole_from_a_new_store(tmp_path):
    """B2's done-when: a scripted Run, a new Store on the same file, and history returns the chat, its messages, its Run and every event."""
    page = ("URL: https://example.com\nTitle: Example\nText: Example Domain", "abc/1.jpg")
    script = [plan("read it", role="browser"), browse("open", "https://example.com"), say("Heading: Example Domain"), say("It says Example Domain.")]
    reopened = await serve(tmp_path, [ask("c1", "read https://example.com")], script, browser=FakeBrowser(page))

    (summary,) = history.list_conversations(reopened)
    assert (summary.id, summary.state, summary.preview) == ("c1", "idle", "It says Example Domain.")

    chat = history.get_conversation(reopened, "c1")
    (r,) = chat.runs
    assert (r.state, r.request, r.cap_usd, r.steps) == ("done", "read https://example.com", 1.0, 4)  # plan, browse, browser answer, orchestrator answer
    assert r.cost_usd == pytest.approx(0.004) and r.started_at <= r.ended_at
    assert chat.messages[1].run_id == r.run_id

    events = history.run_events(reopened, r.run_id)
    assert [e.kind for e in events if e.kind != "plan"] == ["step", "step", "shot", "step", "return", "step"]
    assert all(isinstance(e, TraceFrame) and e.conversation_id == "c1" and e.run_id == r.run_id for e in events)
    planning = next(e for e in events if e.kind == "step")
    assert next(e for e in events if e.kind == "step" and e.role == "browser").parent == planning.id  # the Role's work hangs off the plan step
    shot = next(e for e in events if e.kind == "shot")
    assert shot.data["shot"] == "abc/1.jpg" and (shot.data["url"], shot.data["title"]) == ("https://example.com", "Example")
    assert [e.at for e in events] == sorted(e.at for e in events)  # in the order they were streamed

    TypeAdapter(ConversationDetail).validate_json(chat.model_dump_json())  # what the web channel will send is valid JSON of the contract


async def test_a_stopped_run_reads_as_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")  # no budget: the Run stops before its first model call
    reopened = await serve(tmp_path, [ask("c1", "what is the capital of France?")], [])
    (r,) = history.get_conversation(reopened, "c1").runs
    assert (r.state, r.cap_usd, r.steps) == ("stopped", 0.0, 0)
    assert [e.kind for e in history.run_events(reopened, r.run_id)] == ["stop"]


async def test_a_run_that_has_not_ended_reads_as_running(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    ledger.save_message("c1", "user", "slow one")
    ledger.start_run(Task(user_id="u", request="slow one", conversation_id="c1"), "run1", 1.0)  # started, never ended
    reopened = Store(tmp_path / "t.db")
    assert history.list_conversations(reopened)[0].state == "running"
    assert history.get_conversation(reopened, "c1").runs[0].state == "running"


def test_a_saved_message_keeps_the_id_and_time_it_was_given(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    sent = datetime(2026, 10, 1, 12, 0, 5, tzinfo=timezone.utc)  # in the past, so a message saved "now" sorts after it
    ledger.save_message("c1", "user", "hello", message_id="m" * 32, at=sent)
    ledger.save_message("c1", "assistant", "hi")  # given neither: it gets fresh ones

    first, second = history.get_conversation(Store(tmp_path / "t.db"), "c1").messages
    assert (first.id, first.at) == ("m" * 32, sent)
    assert len(second.id) == 32 and second.id != first.id and second.at >= sent


async def test_the_live_message_and_its_saved_copy_are_one_message(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    inner = FakeChannel(ask("c1", "hello"))
    saved = SavedChannel(inner, ledger)

    (incoming,) = [m async for m in saved.messages()]
    reply = Reply(text="hi", conversation_id="c1")
    await saved.send(reply)

    assert inner.sent == [reply]  # the channel is handed the very Reply that was saved, so it can use reply.id and reply.at for its live frame
    messages = history.get_conversation(Store(tmp_path / "t.db"), "c1").messages
    assert [(m.id, m.at) for m in messages] == [(incoming.id, incoming.at), (reply.id, reply.at)]


def test_every_reply_has_its_own_id_and_an_aware_time():
    a, b = Reply(text="x"), Reply(text="x")
    assert a.id != b.id and len(a.id) == 32 and a.at.tzinfo is not None


def test_a_message_sent_while_a_run_was_busy_sorts_by_when_it_was_sent_and_updated_at_never_moves_back(tmp_path):
    t0 = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    ledger = Ledger(Store(tmp_path / "t.db"))
    ledger.save_message("c1", "user", "first", at=t0)
    ledger.save_message("c1", "assistant", "answer one", at=t0 + timedelta(seconds=30))
    ledger.save_message("c1", "user", "second", at=t0 + timedelta(seconds=5))  # typed during the Run, saved after its reply: the page showed it in this order

    store = Store(tmp_path / "t.db")
    assert [m.text for m in history.get_conversation(store, "c1").messages] == ["first", "second", "answer one"]
    assert history.list_conversations(store)[0].updated_at == t0 + timedelta(seconds=30)
