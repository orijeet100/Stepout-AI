import pytest

from stepout.domain import AnswerAction, FetchAction, Reply, Task
from stepout.ledger import Ledger
from stepout.model import ModelResponse
from stepout.runner import Runner
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel


class FakeFetcher:
    def __init__(self, text: str) -> None:
        self._text = text
        self.urls: list[str] = []

    async def get(self, url: str):
        self.urls.append(url)
        from stepout.fetch import FetchedPage

        return FetchedPage(url=url, text=self._text)


@pytest.fixture
def ledger(tmp_path):
    return Ledger(Store(tmp_path / "test.db"))


def _collector(replies: list[Reply]):
    async def notify(reply: Reply) -> None:
        replies.append(reply)

    return notify


async def test_direct_answer_sends_one_reply(ledger):
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="42"), cost_usd=0.001)])
    replies: list[Reply] = []
    runner = Runner(model, FakeFetcher(""), ledger, _collector(replies))
    task = Task(user_id="u", request="what is 6*7", route="answer")
    await runner.submit(task)
    assert len(replies) == 1
    assert "42" in replies[0].text


async def test_fetch_action_feeds_a_second_model_call(ledger):
    model = ScriptedModel(
        [
            ModelResponse(action=FetchAction(url="https://example.com/weather"), cost_usd=0.001),
            ModelResponse(action=AnswerAction(text="sunny"), cost_usd=0.001),
        ]
    )
    fetcher = FakeFetcher("Chicago: sunny, 70F")
    replies: list[Reply] = []
    runner = Runner(model, fetcher, ledger, _collector(replies))
    task = Task(user_id="u", request="weather in chicago", route="lookup")
    await runner.submit(task)
    assert fetcher.urls == ["https://example.com/weather"]
    assert "sunny" in replies[0].text


async def test_budget_cap_stops_the_run(ledger, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="never reached"), cost_usd=1.0)])
    replies: list[Reply] = []
    runner = Runner(model, FakeFetcher(""), ledger, _collector(replies))
    task = Task(user_id="u", request="x", route="answer")
    await runner.submit(task)
    assert "budget" in replies[0].text.lower()
    assert len(model.requests) == 0
