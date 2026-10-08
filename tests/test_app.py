import pytest

from stepout.app import run
from stepout.domain import AnswerAction, Decline, Message, Proceed, Reply
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.runner import Runner
from stepout.store import Store
from tests.support.screeners import FixedScreener
from tests.support.scripted_model import ScriptedModel

NO_PAYMENTS = Decline(reason="That means paying someone.", alternative="I can look things up.")


class FakeChannel:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.sent: list[Reply] = []

    async def messages(self):
        for text in self._texts:
            yield Message(user_id="u", text=text)

    async def send(self, reply: Reply) -> None:
        self.sent.append(reply)


class FakeFetcher:
    async def get(self, url: str):  # pragma: no cover - not exercised in this test
        raise AssertionError("fetch not expected")


@pytest.fixture
def ledger(tmp_path):
    return Ledger(Store(tmp_path / "test.db"))


async def test_declined_request_end_to_end(ledger):
    channel = FakeChannel(["pay this invoice"])
    model = ScriptedModel([])
    runner = Runner(model, FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener((NO_PAYMENTS, 0.0009)), ledger), runner)
    assert [(r.text, r.cost_usd) for r in channel.sent] == [("That means paying someone. I can look things up.", 0.0009)]
    assert model.requests == []  # a decline never reaches the Orchestrator


class BoomModel:
    async def call(self, request):
        raise RuntimeError("provider down")


async def test_a_failed_request_does_not_end_the_session(ledger):
    channel = FakeChannel(["what is the capital of France?", "pay this invoice"])
    runner = Runner(BoomModel(), FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener((Proceed(), 0.0), (NO_PAYMENTS, 0.0)), ledger), runner)
    assert "went wrong" in channel.sent[0].text
    assert "paying" in channel.sent[1].text  # the next request was still served


async def test_answer_request_end_to_end(ledger):
    channel = FakeChannel(["what is the capital of France?"])
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="Paris"), cost_usd=0.002)])
    runner = Runner(model, FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener((Proceed(), 0.0007)), ledger), runner)
    assert len(channel.sent) == 1
    assert "Paris" in channel.sent[0].text
    assert channel.sent[0].text == "Paris" and channel.sent[0].cost_usd == pytest.approx(0.0027)  # the front door's $0.0007 is in the total, and the text carries no footer
