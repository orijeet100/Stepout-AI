import pytest

from stepout.app import run
from stepout.domain import AnswerAction, Message, Reply
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.runner import Runner
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel


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
    intake = Intake(ScriptedModel([]), ledger)
    runner = Runner(ScriptedModel([]), FakeFetcher(), ledger, channel.send)
    await run(channel, intake, runner)
    assert len(channel.sent) == 1
    assert "pay" in channel.sent[0].text.lower() or "I can" in channel.sent[0].text


class BoomModel:
    async def call(self, request):
        raise RuntimeError("provider down")


async def test_a_failed_request_does_not_end_the_session(ledger):
    channel = FakeChannel(["what is the capital of France?", "pay this invoice"])
    runner = Runner(BoomModel(), FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(ScriptedModel([]), ledger), runner)
    assert "went wrong" in channel.sent[0].text
    assert "payments" in channel.sent[1].text  # the next request was still served


async def test_answer_request_end_to_end(ledger):
    channel = FakeChannel(["what is the capital of France?"])
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="Paris"), cost_usd=0.002)])
    intake = Intake(model, ledger)
    runner = Runner(model, FakeFetcher(), ledger, channel.send)
    await run(channel, intake, runner)
    assert len(channel.sent) == 1
    assert "Paris" in channel.sent[0].text
