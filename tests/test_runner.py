import asyncio

import httpx
import pytest

from stepout.domain import AnswerAction, BrowseAction, DelegateAction, FetchAction, FilesAction, PlanAction, PlanStep, Reply, Task
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


class FakeBrowser:
    def __init__(self, *pages) -> None:
        self.pages, self.calls, self.closed = list(pages), [], []

    async def run(self, run_id, op, url=None, link=None):
        self.calls.append((run_id, op, url, link))
        return self.pages.pop(0)

    async def close(self, run_id):
        self.closed.append(run_id)


class FakeFiles:
    def __init__(self, result="") -> None:
        self.result, self.calls = result, []

    async def run(self, op, path, pattern=None, cancelled=lambda: False):
        self.calls.append((op, path, pattern, cancelled))
        return self.result


def say(text, cost=0.001, **kw):
    return ModelResponse(action=AnswerAction(text=text), cost_usd=cost, **kw)


def plan(*goals, cost=0.001, role="direct"):
    return ModelResponse(action=PlanAction(steps=[PlanStep(role=role, goal=g) for g in goals]), cost_usd=cost)


def delegate(i, cost=0.001):
    return ModelResponse(action=DelegateAction(step=i), cost_usd=cost)


def fetch(url, cost=0.001):
    return ModelResponse(action=FetchAction(url=url), cost_usd=cost)


def browse(op, url=None, link=None, cost=0.001):
    return ModelResponse(action=BrowseAction(op=op, url=url, link=link), cost_usd=cost)


def looks(op, path, pattern=None, cost=0.001):
    return ModelResponse(action=FilesAction(op=op, path=path, pattern=pattern), cost_usd=cost)


class Harness:
    """Script order = call order. A plan runs its first step itself, so its Role's calls come right after the plan."""

    def __init__(self, tmp_path, responses, fetcher=None, cancel=None, files=None, browser=None):
        self.ledger = Ledger(Store(tmp_path / "t.db"))
        self.model = ScriptedModel(responses)
        self.fetcher = fetcher or FakeFetcher("page text")
        self.replies: list[Reply] = []
        self.traced = []
        self.runner = Runner(self.model, self.fetcher, self.ledger, self._notify, self._trace, cancel, files=files, browser=browser or FakeBrowser())

    async def _notify(self, reply):
        self.replies.append(reply)

    async def _trace(self, event):
        self.traced.append(event)

    async def run(self, request="do it") -> Task:
        task = Task(user_id="u", request=request)
        await self.runner.submit(task)
        return task

    def seen_by(self, i):
        return self.model.requests[i].user_text


async def test_the_orchestrator_can_answer_without_delegating(tmp_path):
    h = Harness(tmp_path, [say("5")])
    await h.run("what is 2+3")
    assert len(h.replies) == 1 and "5" in h.replies[0].text
    assert len(h.model.requests) == 1 and h.model.requests[0].model == SONNET


async def test_a_plan_starts_its_first_step_by_itself(tmp_path):
    h = Harness(tmp_path, [plan("find the weather"), fetch("https://example.com/w"), say("sunny [src](https://example.com/w)"), say("It is sunny.")])
    task = await h.run("weather?")

    assert h.fetcher.urls == ["https://example.com/w"]
    assert h.replies[-1].text.startswith("It is sunny.")
    # Orchestrator plans (Sonnet) -> Direct works (Haiku) -> Orchestrator reports: no call spent on "delegate"
    assert [r.model for r in h.model.requests] == [SONNET, HAIKU, HAIKU, SONNET]
    assert "sunny [src]" in h.seen_by(3) and "[done] direct" in h.seen_by(3)  # the Orchestrator saw the Finding
    assert "Plan:" not in h.seen_by(1)  # the specialist never sees the plan

    events = h.ledger.query(task.id)
    planning = next(e for e in events if e.kind == "step" and e.data["action"]["kind"] == "plan")
    direct_steps = [e for e in events if e.kind == "step" and e.role == "direct"]
    assert direct_steps and all(e.parent == planning.id for e in direct_steps)
    assert [e for e in events if e.kind == "return"][0].data["ok"] is True
    assert [s["status"] for s in [e for e in events if e.kind == "plan"][-1].data["steps"]] == ["done"]


async def test_later_steps_are_delegated_one_at_a_time(tmp_path):
    h = Harness(tmp_path, [plan("a", "b"), say("A done"), delegate(1), say("B done"), say("both")])
    task = await h.run()
    assert [r.model for r in h.model.requests] == [SONNET, HAIKU, SONNET, HAIKU, SONNET]
    assert "[done] direct: a" in h.seen_by(2) and "[pending] direct: b" in h.seen_by(2)
    assert "A done" in h.seen_by(4) and "B done" in h.seen_by(4)
    last_plan = [e for e in h.ledger.query(task.id) if e.kind == "plan"][-1]
    assert [s["status"] for s in last_plan.data["steps"]] == ["done", "done"]


async def test_trace_gets_exactly_what_the_ledger_records(tmp_path):
    h = Harness(tmp_path, [plan("a"), say("found"), say("done")])
    task = await h.run()
    assert [e.id for e in h.traced] == [e.id for e in h.ledger.query(task.id)]
    assert all(e.data["summary"] for e in h.traced)
    assert "direct: a" in next(e for e in h.traced if e.kind == "step").data["summary"]  # the plan line names its steps


async def test_a_specialist_cannot_take_the_orchestrators_actions(tmp_path):
    h = Harness(tmp_path, [plan("a"), plan("sneaky"), say("found"), say("done")])
    task = await h.run()
    assert "Refused" in h.seen_by(2)  # Direct is told why and carries on
    refused = [e for e in h.ledger.query(task.id) if e.kind == "step" and e.data["verdict"] == "refuse"]
    assert len(refused) == 1 and refused[0].role == "direct"
    assert h.replies[-1].text.startswith("done")


async def test_the_budget_is_shared_across_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0.05")
    # The plan alone spends $0.06: the step it starts must not get a model call of its own.
    h = Harness(tmp_path, [plan("a", cost=0.06), say("never reached")])
    await h.run()
    assert len(h.model.requests) == 1
    assert "budget" in h.replies[0].text.lower()


async def test_a_zero_budget_makes_no_model_call(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")
    h = Harness(tmp_path, [say("never reached")])
    await h.run()
    assert len(h.model.requests) == 0 and "budget" in h.replies[0].text.lower()


async def test_searches_left_shrinks_as_they_are_used(tmp_path):
    h = Harness(tmp_path, [plan("a"), say("found", searches=2), say("done")])
    await h.run()
    assert [r.max_searches for r in h.model.requests] == [3, 3, 1]


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
    h = Harness(tmp_path, [plan("1"), say("f"), plan("2"), say("f"), plan("3"), say("f"), plan("4"), say("giving up")])
    await h.run()
    assert "re-planned enough" in h.seen_by(7)  # the fourth plan is refused, so it starts nothing
    assert h.replies[0].text.startswith("giving up")


async def test_delegating_to_a_missing_step_is_refused(tmp_path):
    h = Harness(tmp_path, [plan("a"), say("found"), delegate(5), say("ok")])
    await h.run()
    assert "no step 5" in h.seen_by(3)


@pytest.mark.parametrize("error", [BlockedUrl("private address"), httpx.ConnectError("down")])
async def test_a_failed_fetch_is_reported_to_the_agent_not_raised(tmp_path, error):
    h = Harness(tmp_path, [plan("a"), fetch("http://10.0.0.1/"), say("could not read it"), say("sorry")], fetcher=FakeFetcher(error=error))
    task = await h.run()
    assert "failed" in h.seen_by(2)
    assert h.replies[0].text.startswith("sorry")
    assert any(e.kind == "return" for e in h.ledger.query(task.id))


async def test_an_agent_that_never_finishes_fails_its_step(tmp_path):
    h = Harness(tmp_path, [plan("a")] + [fetch("https://example.com")] * 4 + [say("could not")])
    task = await h.run()
    ret = next(e for e in h.ledger.query(task.id) if e.kind == "return")
    assert ret.data["ok"] is False and "couldn't finish" in ret.data["summary"]


async def test_the_files_agent_looks_at_the_disk_and_the_orchestrator_reports(tmp_path):
    files = FakeFiles("D:\\: 12 files, 3 folders")
    h = Harness(tmp_path, [plan("count D:", role="files"), looks("count", "D:\\"), say("12 files, 3 folders"), say("You have 12 files.")], files=files)
    await h.run("how many files on D?")
    assert files.calls[0][:3] == ("count", "D:\\", None)
    assert h.model.requests[1].tools == ["files"] and h.model.requests[1].model == HAIKU
    assert "12 files, 3 folders" in h.seen_by(2)  # the Files agent saw the result
    assert "12 files, 3 folders" in h.seen_by(3)  # and the Orchestrator saw its Finding
    assert h.replies[0].text.startswith("You have 12 files.")
    h.runner._cancel.set()
    assert files.calls[0][3]() is True  # the walk polls the same Stop flag


async def test_the_files_agent_cannot_fetch_and_the_direct_agent_cannot_look_at_the_disk(tmp_path):
    h = Harness(tmp_path, [plan("a", role="files"), fetch("https://example.com"), say("ok"), say("done")])
    task = await h.run()
    assert h.fetcher.urls == []
    assert any(e.data["verdict"] == "refuse" and e.role == "files" for e in h.ledger.query(task.id) if e.kind == "step")

    (tmp_path / "2").mkdir()
    files = FakeFiles("never")
    h = Harness(tmp_path / "2", [plan("a"), looks("list", "D:\\"), say("ok"), say("done")], files=files)
    await h.run()
    assert files.calls == []


async def test_repeating_an_identical_hand_action_is_not_run_again(tmp_path):
    files = FakeFiles("nothing")
    same = looks("find", "D:\\Docs", "resume")
    h = Harness(tmp_path, [plan("a", role="files"), same, same, looks("find", "D:\\Work", "resume"), say("not found"), say("done")], files=files)
    await h.run()
    assert [c[1] for c in files.calls] == ["D:\\Docs", "D:\\Work"]  # the repeat never reached the disk
    assert "already ran exactly this" in h.seen_by(3)


async def test_the_browser_agent_reads_a_page_and_its_screenshot_reaches_the_trace(tmp_path):
    browser = FakeBrowser(("URL: https://example.com\nTitle: Example\nText: Example Domain", "abc/1.jpg"))
    h = Harness(tmp_path, [plan("read example.com", role="browser"), browse("open", "https://example.com"), say("The heading is Example Domain"), say("It says Example Domain.")], browser=browser)
    task = await h.run("what does example.com say?")
    assert browser.calls[0][1:] == ("open", "https://example.com", None)
    assert h.model.requests[1].tools == ["browse"] and h.model.requests[1].model == SONNET
    assert "Example Domain" in h.seen_by(2)  # the Browser agent saw the page
    assert "Example Domain" in h.seen_by(3)  # and the Orchestrator its Finding
    shot = next(e for e in h.ledger.query(task.id) if e.kind == "shot")
    assert shot.data["shot"] == "abc/1.jpg" and shot.role == "browser"


async def test_only_the_newest_pages_stay_in_a_roles_notes(tmp_path):
    pages = [(f"URL: https://x/{i}\nTitle: T{i}\nText: body {i}", None) for i in range(3)]
    h = Harness(tmp_path, [plan("a", role="browser"), browse("open", "https://x/0"), browse("click", link=1), browse("click", link=1), say("done"), say("ok")], browser=FakeBrowser(*pages))
    await h.run()
    last = h.seen_by(4)  # the Browser agent's request after its third page
    assert "(earlier page) URL: https://x/0" in last and "body 0" not in last
    assert "body 1" in last and "body 2" in last  # the previous and the current page stay in full


async def test_a_runs_browser_session_is_closed_even_when_the_run_fails(tmp_path):
    browser = FakeBrowser()
    h = Harness(tmp_path, [], browser=browser)  # no scripted responses: the model call raises
    with pytest.raises(IndexError):
        await h.run()
    assert len(browser.closed) == 1


async def test_roles_hold_only_their_own_hand(tmp_path):
    h = Harness(tmp_path, [plan("a", role="browser"), fetch("https://example.com"), say("ok"), say("done")])
    task = await h.run()
    assert h.fetcher.urls == []  # the Browser agent cannot use the Fetcher
    assert any(e.data["verdict"] == "refuse" and e.role == "browser" for e in h.ledger.query(task.id) if e.kind == "step")
