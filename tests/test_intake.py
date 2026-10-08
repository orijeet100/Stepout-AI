import pytest

from stepout.domain import ChatReply, Decline, Exchange, Message, Proceed
from stepout.intake import ChatReading, CommandReading, DeclinedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.store import Store
from tests.support.screeners import FixedScreener


@pytest.fixture
def ledger(tmp_path):
    return Ledger(Store(tmp_path / "test.db"))


def xs(*ids):
    return [Exchange(id=i, request=f"request {i}", reply=f"reply {i}", did="", run_id=f"r{i}") for i in ids]


def said(text, cid="c1"):
    return Message(user_id="u", text=text, conversation_id=cid)


async def test_a_command_never_reaches_the_front_door(ledger):
    screener = FixedScreener()
    reading = await Intake(screener, ledger).read(said("/status"))
    assert isinstance(reading, CommandReading) and reading.name == "status"
    assert screener.calls == []  # no call, no cost


async def test_a_decline_carries_its_reason_alternative_and_cost(ledger):
    intake = Intake(FixedScreener((Decline(reason="That means paying someone.", alternative="I can look things up."), 0.0009)), ledger)
    reading = await intake.read(said("pay my rent"))
    assert reading == DeclinedReading(reason="That means paying someone.", alternative="I can look things up.", cost_usd=0.0009)


async def test_plain_chat_is_answered_without_a_task(ledger):
    reading = await Intake(FixedScreener((ChatReply(text="Hello!"), 0.0006)), ledger).read(said("hi"))
    assert reading == ChatReading(text="Hello!", cost_usd=0.0006)


async def test_proceed_carries_only_the_linked_exchanges_oldest_first(ledger):
    screener = FixedScreener((Proceed(related=[3, 1]), 0.0008))
    intake = Intake(screener, ledger, lambda cid: xs(1, 2, 3))
    reading = await intake.read(said("that site again"))
    assert isinstance(reading, NewTask) and reading.request == "that site again" and reading.cost_usd == 0.0008
    assert [x.id for x in reading.previous] == [1, 3]  # not 2
    assert [x.id for x in screener.calls[0][1]] == [1, 2, 3]  # it was shown all of them


async def test_a_new_task_carries_no_history(ledger):
    reading = await Intake(FixedScreener((Proceed(related=[]), 0.0008)), ledger, lambda cid: xs(1, 2)).read(said("something new"))
    assert reading.previous == []


async def test_the_chats_own_exchanges_are_looked_up_by_conversation(ledger):
    asked = []
    await Intake(FixedScreener(), ledger, lambda cid: asked.append(cid) or []).read(said("hello there", cid="chat-9"))
    assert asked == ["chat-9"]


@pytest.mark.parametrize("answer", [(None, 0.0007), RuntimeError("API down")], ids=["unusable answer", "call failed"])
async def test_when_the_front_door_fails_the_message_proceeds_with_the_last_three_exchanges(ledger, answer):
    reading = await Intake(FixedScreener(answer), ledger, lambda cid: xs(1, 2, 3, 4)).read(said("go on"))
    assert isinstance(reading, NewTask) and [x.id for x in reading.previous] == [2, 3, 4]
    assert reading.cost_usd == (0.0007 if isinstance(answer, tuple) else 0.0)  # an unusable answer still cost money
    (event,) = [e for e in ledger.query() if e.kind == "screening_fallback"]
    assert event.conversation_id == "c1" and event.data["request"] == "go on" and event.cost_usd == reading.cost_usd
    assert event.data["failure"] == ("the answer was not usable" if isinstance(answer, tuple) else "RuntimeError")
    assert not any(e.kind == "screening" for e in ledger.query())  # one record per message


async def test_every_decision_is_recorded_with_its_chat_and_cost(ledger):
    intake = Intake(FixedScreener((Proceed(related=[2]), 0.0008), (ChatReply(text="hi"), 0.0006)), ledger, lambda cid: xs(1, 2))
    await intake.read(said("again", cid="c1"))
    await intake.read(said("hello", cid="c2"))
    first, second = [e for e in ledger.query() if e.kind == "screening"]
    assert (first.conversation_id, first.data, first.cost_usd) == ("c1", {"request": "again", "decision": "proceed", "related": [2]}, 0.0008)
    assert (second.conversation_id, second.data["decision"], second.cost_usd) == ("c2", "chat", 0.0006)
