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
    assert "unexpected problem" in channel.sent[0].text and "RuntimeError" not in channel.sent[0].text  # a plain line, not the exception class
    assert "paying" in channel.sent[1].text  # the next request was still served


async def test_answer_request_end_to_end(ledger):
    channel = FakeChannel(["what is the capital of France?"])
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="Paris"), cost_usd=0.002)])
    runner = Runner(model, FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener((Proceed(), 0.0007)), ledger), runner)
    assert len(channel.sent) == 1
    assert "Paris" in channel.sent[0].text
    assert channel.sent[0].text == "Paris" and channel.sent[0].cost_usd == pytest.approx(0.0027)  # Screening's $0.0007 is in the total, and the text carries no footer


def test_the_browser_sends_live_frames_to_a_channel_that_shows_them_and_captures_nothing_for_one_that_does_not():
    from types import SimpleNamespace

    from stepout.app import make_browser
    from stepout.channels.cli import CliChannel

    def live_frame(run_id, jpeg): ...

    assert make_browser(SimpleNamespace(live_frame=live_frame))._on_frame is live_frame  # the channel's own method, unwrapped
    assert make_browser(CliChannel())._on_frame is None  # the terminal has none


# --- the month's limit ---


async def test_a_message_at_the_months_limit_is_answered_with_a_line_and_costs_nothing(ledger):
    channel = FakeChannel(["what is the capital of France?"])
    model = ScriptedModel([])
    runner = Runner(model, FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener(), ledger), runner, month_left=lambda: 0.0)
    assert len(channel.sent) == 1 and "spending limit" in channel.sent[0].text and "STEPOUT_MONTH_CAP_USD" in channel.sent[0].text
    assert model.requests == [] and ledger.query() == []  # no screening call, nothing recorded


async def test_a_slash_command_still_works_at_the_limit(ledger):
    channel = FakeChannel(["/what"])
    runner = Runner(ScriptedModel([]), FakeFetcher(), ledger, channel.send)
    await run(channel, Intake(FixedScreener(), ledger), runner, month_left=lambda: 0.0)
    assert channel.sent[0].text == "Unknown command: /what"


async def test_a_run_may_not_spend_more_than_the_month_has_left(ledger):
    channel = FakeChannel(["what is the capital of France?"])
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="Paris"), cost_usd=0.002)])
    runner = Runner(model, FakeFetcher(), ledger, channel.send, month_left=lambda: 0.25)
    await run(channel, Intake(FixedScreener((Proceed(), 0.0)), ledger), runner, month_left=lambda: 0.25)
    (row,) = ledger._store.query("SELECT cap_usd FROM runs")
    assert row["cap_usd"] == pytest.approx(0.25)  # the per-Run cap is $1.00
