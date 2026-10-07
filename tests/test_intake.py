import pytest

from stepout.domain import AnswerAction, Message
from stepout.intake import CommandReading, DeclinedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel


@pytest.fixture
def ledger(tmp_path):
    return Ledger(Store(tmp_path / "test.db"))


async def test_command_is_fast_path(ledger):
    intake = Intake(ScriptedModel([]), ledger)
    reading = await intake.read(Message(user_id="u", text="/status"))
    assert isinstance(reading, CommandReading)
    assert reading.name == "status"


async def test_forbidden_request_is_declined(ledger):
    intake = Intake(ScriptedModel([]), ledger)
    reading = await intake.read(Message(user_id="u", text="please pay this invoice"))
    assert isinstance(reading, DeclinedReading)


async def test_lookup_hint_skips_the_model(ledger):
    intake = Intake(ScriptedModel([]), ledger)
    reading = await intake.read(Message(user_id="u", text="what's the weather today?"))
    assert isinstance(reading, NewTask)
    assert reading.route == "lookup"


async def test_unsure_text_falls_back_to_cheap_model(ledger):
    scripted = ScriptedModel([ModelResponse(action=AnswerAction(text="answer"), cost_usd=0.001)])
    intake = Intake(scripted, ledger)
    reading = await intake.read(Message(user_id="u", text="hi"))
    assert isinstance(reading, NewTask)
    assert reading.route == "answer"
    assert len(scripted.requests) == 1


async def test_screening_is_recorded_in_the_ledger(ledger):
    intake = Intake(ScriptedModel([]), ledger)
    await intake.read(Message(user_id="u", text="please pay this invoice"))
    events = ledger.query()
    assert any(e.kind == "screening" for e in events)
