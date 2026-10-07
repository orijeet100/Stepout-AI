import asyncio

import pytest

from stepout.domain import AnswerAction, DelegateAction, FetchAction, FilesAction, PlanAction, PlanStep, Reply, Task
from stepout.fetch import BlockedUrl, FetchedPage
from stepout.ledger import Ledger
from stepout.model import HAIKU, SONNET, ModelResponse
from stepout.runner import Runner
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel


class FakeFetcher:
    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self._text, self._error = text, error
        self.urls: list[str] = []

    async def get(self, url: str):
        self.urls.append(url)
        if self._error:
            raise self._error
        return FetchedPage(url=url, text=self._text)


def say(text, cost=0.001, **kw):
    return ModelResponse(action=AnswerAction(text=text), cost_usd=cost, **kw)


def plan(*goals, cost=0.001, role="direct"):
    return ModelResponse(action=PlanAction(steps=[PlanStep(role=role, goal=g) for g in goals]), cost_usd=cost)


def delegate(i, cost=0.001):
    return ModelResponse(action=DelegateAction(step=i), cost_usd=cost)


def fetch(url, cost=0.001):
    return ModelResponse(action=FetchAction(url=url), cost_usd=cost)


def looks(op, path, pattern=None, cost=0.001):
    return ModelResponse(action=FilesAction(op=op, path=path, pattern=pattern), cost_usd=cost)


class FakeFiles:
    def __init__(self, result="") -> None:
        self.result, self.calls = result, []

    async def run(self, op, path, pattern=None, cancelled=lambda: False):
        self.calls.append((op, path, pattern, cancelled))
        return self.result


class Harness:
    def __init__(self, tmp_path, responses, fetcher=None, cancel=None, files=None):
        self.ledger = Ledger(Store(tmp_path / "t.db"))
        self.model = ScriptedModel(responses)
        self.fetcher = fetcher or FakeFetcher("page text")
        self.replies: list[Reply] = []
        self.traced = []
        self.runner = Runner(self.model, self.fetcher, self.ledger, self._notify, self._trace, cancel, files=files)

    async def _notify(self, reply):
        self.replies.append(reply)

    async def _trace(self, event):
        self.traced.append(event)

    async def run(self, request="do it") -> Task:
        task = Task(user_id="u", request=request, route="answer")
        await self.runner.submit(task)
        return task

    def seen_by(self, i):
        return self.model.requests[i].user_text


async def test_the_orchestrator_can_answer_without_delegating(tmp_path):
    h = Harness(tmp_path, [say("5")])
    await h.run("what is 2+3")
    assert len(h.replies) == 1 and "5" in h.replies[0].text
    assert len(h.model.requests) == 1 and h.model.requests[0].model == SONNET


async def test_plan_delegate_fetch_report(tmp_path):
    h = Harness(
        tmp_path,
        [plan("find the weather"), delegate(0), fetch("https://example.com/w"), say("sunny [src](https://example.com/w)"), say("It is sunny.")],
    )
    task = await h.run("weather?")

    assert h.fetcher.urls == ["https://example.com/w"]
    assert h.replies[-1].text.startswith("It is sunny.")
    # Orchestrator (Sonnet) -> Direct (Haiku) and back
    assert [r.model for r in h.model.requests] == [SONNET, SONNET, HAIKU, HAIKU, SONNET]
    # the Orchestrator saw the Finding, and its plan marked done
    assert "sunny [src]" in h.seen_by(4) and "[done] direct" in h.seen_by(4)
    # the specialist never sees the plan or the other Role's notes
    assert "Plan:" not in h.seen_by(2)

    events = h.ledger.query(task.id)
    delegating = next(e for e in events if e.kind == "step" and e.data["action"]["kind"] == "delegate")
    direct_steps = [e for e in events if e.kind == "step" and e.role == "direct"]
    assert direct_steps and all(e.parent == delegating.id for e in direct_steps)
    assert [e for e in events if e.kind == "return"][0].data["ok"] is True
    assert [s["status"] for s in [e for e in events if e.kind == "plan"][-1].data["steps"]] == ["done"]


async def test_trace_gets_exactly_what_the_ledger_records(tmp_path):
    h = Harness(tmp_path, [plan("a"), delegate(0), say("found"), say("done")])
    task = await h.run()
    assert [e.id for e in h.traced] == [e.id for e in h.ledger.query(task.id)]
    assert all(e.data["summary"] for e in h.traced)


async def test_a_specialist_cannot_take_the_orchestrators_actions(tmp_path):
    h = Harness(tmp_path, [plan("a"), delegate(0), plan("sneaky"), say("found"), say("done")])
    task = await h.run()
    assert "Refused" in h.seen_by(3)  # Direct is told why and carries on
    refused = [e for e in h.ledger.query(task.id) if e.kind == "step" and e.data["verdict"] == "refuse"]
    assert len(refused) == 1 and refused[0].role == "direct"
    assert h.replies[-1].text.startswith("done")


async def test_the_budget_is_shared_across_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0.05")
    # Orchestrator spends $0.06 over two calls; the Direct agent must not get a call of its own.
    h = Harness(tmp_path, [plan("a", cost=0.03), delegate(0, cost=0.03), say("never reached")])
    await h.run()
    assert len(h.model.requests) == 2
    assert "budget" in h.replies[0].text.lower()


async def test_a_zero_budget_makes_no_model_call(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")
    h = Harness(tmp_path, [say("never reached")])
    await h.run()
    assert len(h.model.requests) == 0 and "budget" in h.replies[0].text.lower()


async def test_searches_left_shrinks_as_they_are_used(tmp_path):
    h = Harness(tmp_path, [plan("a"), delegate(0), say("found", searches=2), say("done")])
    await h.run()
    assert [r.max_searches for r in h.model.requests] == [3, 3, 3, 1]


async def test_stop_ends_the_run_between_steps(tmp_path):
    cancel = asyncio.Event()

    class StopsAfterFirstCall(ScriptedModel):
        async def call(self, request):
            response = await super().call(request)
            cancel.set()  # the User presses Stop while the model is thinking
            return response

    h = Harness(tmp_path, [], cancel=cancel)
    h.model = StopsAfterFirstCall([plan("a"), say("never reached")])
    h.runner._model = h.model
    task = await h.run()
    assert len(h.model.requests) == 1
    assert "stopped by you" in h.replies[0].text.lower()
    assert [e.kind for e in h.ledger.query(task.id)][-1] == "stop"


async def test_a_new_run_starts_unstopped(tmp_path):
    cancel = asyncio.Event()
    cancel.set()  # a stale Stop from before this request
    h = Harness(tmp_path, [say("fine")], cancel=cancel)
    await h.run()
    assert h.replies[0].text.startswith("fine")


async def test_replanning_is_limited(tmp_path):
    h = Harness(tmp_path, [plan("1"), plan("2"), plan("3"), plan("4"), say("giving up")])
    await h.run()
    assert "re-planned enough" in h.seen_by(4)
    assert h.replies[0].text.startswith("giving up")


async def test_delegating_to_a_missing_step_is_refused(tmp_path):
    h = Harness(tmp_path, [plan("a"), delegate(5), say("ok")])
    await h.run()
    assert "no step 5" in h.seen_by(2)


@pytest.mark.parametrize("error", [BlockedUrl("private address"), __import__("httpx").ConnectError("down")])
async def test_a_failed_fetch_is_reported_to_the_agent_not_raised(tmp_path, error):
    h = Harness(tmp_path, [plan("a"), delegate(0), fetch("http://10.0.0.1/"), say("could not read it"), say("sorry")], fetcher=FakeFetcher(error=error))
    task = await h.run()
    assert "failed" in h.seen_by(3)
    assert h.replies[0].text.startswith("sorry")
    assert any(e.kind == "return" for e in h.ledger.query(task.id))


async def test_an_agent_that_never_finishes_fails_its_step(tmp_path):
    h = Harness(tmp_path, [plan("a"), delegate(0)] + [fetch("https://example.com")] * 4 + [say("could not")])
    task = await h.run()
    ret = next(e for e in h.ledger.query(task.id) if e.kind == "return")
    assert ret.data["ok"] is False and "couldn't finish" in ret.data["summary"]


async def test_the_files_agent_looks_at_the_disk_and_the_orchestrator_reports(tmp_path):
    files = FakeFiles("D:\\: 12 files, 3 folders")
    h = Harness(
        tmp_path,
        [plan("count D:", role="files"), delegate(0), looks("count", "D:\\"), say("12 files, 3 folders"), say("You have 12 files.")],
        files=files,
    )
    await h.run("how many files on D?")
    assert files.calls[0][:3] == ("count", "D:\\", None)
    assert h.model.requests[2].tools == ["files"] and h.model.requests[2].model == HAIKU
    assert "12 files, 3 folders" in h.seen_by(3)  # the Files agent saw the result
    assert "12 files, 3 folders" in h.seen_by(4)  # and the Orchestrator saw its Finding
    assert h.replies[0].text.startswith("You have 12 files.")
    h.runner._cancel.set()
    assert files.calls[0][3]() is True  # the walk polls the same Stop flag


async def test_the_files_agent_cannot_fetch_and_the_direct_agent_cannot_look_at_the_disk(tmp_path):
    h = Harness(tmp_path, [plan("a", role="files"), delegate(0), fetch("https://example.com"), say("ok"), say("done")])
    task = await h.run()
    assert h.fetcher.urls == []
    assert any(e.data["verdict"] == "refuse" and e.role == "files" for e in h.ledger.query(task.id) if e.kind == "step")

    files = FakeFiles("never")
    h = Harness(tmp_path / "2", [plan("a"), delegate(0), looks("list", "D:\\"), say("ok"), say("done")], files=files)
    (tmp_path / "2").mkdir(exist_ok=True)
    await h.run()
    assert files.calls == []
