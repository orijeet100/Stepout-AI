"""Chats are saved: they survive a restart and stay apart (v0: messages only, no runs table yet)."""

import sqlite3

from stepout import history
from stepout.app import SavedChannel, run
from stepout.domain import AnswerAction, Message, Reply
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.runner import Runner
from stepout.store import _MIGRATIONS_DIR, Store
from tests.support.scripted_model import ScriptedModel


def test_a_0002_database_upgrades_to_the_latest_without_losing_events(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    for name in ("0001_init.sql", "0002_event_role_parent.sql"):
        conn.executescript((_MIGRATIONS_DIR / name).read_text())
    conn.execute("PRAGMA user_version = 2")
    conn.execute("INSERT INTO events (id, kind, data, at, role) VALUES ('e1', 'step', '{}', '2026-10-01T00:00:00', 'direct')")
    conn.commit()
    conn.close()

    store = Store(path)
    assert store.query("PRAGMA user_version")[0][0] == len(list(_MIGRATIONS_DIR.glob("*.sql")))  # every migration ran
    old = Ledger(store).query()[0]
    assert (old.id, old.role, old.conversation_id) == ("e1", "direct", None)  # kept, and not in any chat
    assert history.list_conversations(store) == []


def test_saved_messages_come_back_in_order_from_a_new_store(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    ledger.save_message("a", "user", "what is the capital of France?")
    ledger.save_message("a", "assistant", "Paris")
    ledger.save_message("b", "user", "x" * 100)

    reopened = Store(tmp_path / "t.db")  # as after a restart
    chat = history.get_conversation(reopened, "a")
    assert chat["title"] == "what is the capital of France?"
    assert [(m["role"], m["text"]) for m in chat["messages"]] == [("user", "what is the capital of France?"), ("assistant", "Paris")]
    assert [c["id"] for c in history.list_conversations(reopened)] == ["b", "a"]  # newest first
    assert history.list_conversations(reopened)[0]["title"] == "x" * 60  # the first message, cut to 60
    assert history.get_conversation(reopened, "nope") is None
    assert len(history.get_conversation(reopened, "b")["messages"]) == 1  # chats stay apart


class FakeChannel:
    def __init__(self, *messages: Message) -> None:
        self._messages, self.sent = messages, []

    async def messages(self):
        for m in self._messages:
            yield m

    async def send(self, reply: Reply) -> None:
        self.sent.append(reply)


class NoFetcher:
    async def get(self, url):  # pragma: no cover - these requests never fetch
        raise AssertionError("fetch not expected")


async def test_a_conversation_through_the_app_is_saved_and_survives_a_restart(tmp_path):
    ask = lambda cid, text: Message(user_id="u", text=text, conversation_id=cid)
    channel = FakeChannel(ask("a", "what is the capital of France?"), ask("b", "what is the capital of Spain?"), ask("a", "pay this invoice"))
    ledger = Ledger(Store(tmp_path / "t.db"))
    model = ScriptedModel([ModelResponse(action=AnswerAction(text=t), cost_usd=0.001) for t in ("Paris", "Madrid")])
    saved = SavedChannel(channel, ledger)
    await run(saved, Intake(model, ledger), Runner(model, NoFetcher(), ledger, saved.send))

    assert [r.conversation_id for r in channel.sent] == ["a", "b", "a"]  # each reply goes back to its own chat

    reopened = Store(tmp_path / "t.db")  # as after a restart
    a, b = (history.get_conversation(reopened, c) for c in "ab")
    head = lambda m: (m["role"], m["text"].splitlines()[0])  # an answer ends with a cost footer; compare its first line
    assert [head(m) for m in a["messages"]] == [
        ("user", "what is the capital of France?"),
        ("assistant", "Paris"),
        ("user", "pay this invoice"),
        ("assistant", "That's payments and transfers, which I won't do. I can look things up, fetch public pages, and answer questions — just not that."),
    ]  # a decline is saved too
    assert [head(m) for m in b["messages"]] == [("user", "what is the capital of Spain?"), ("assistant", "Madrid")]
    assert (a["title"], b["title"]) == ("what is the capital of France?", "what is the capital of Spain?")
    assert reopened.query("SELECT COUNT(*) FROM events WHERE conversation_id IS NULL")[0][0] == 0  # every event belongs to a chat
    assert {r["kind"] for r in reopened.query("SELECT kind FROM events WHERE conversation_id = 'b'")} == {"message", "screening", "step"}
