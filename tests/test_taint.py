"""Strict taint: once a Run has been handed the contents of a file, the web is closed to it, whichever Role asks.

File text is written by anyone and may carry instructions; the web is the way out. These tests drive the real Runner, Gate and Reader
(real files and PDFs made in the test) with a scripted model, and check what reaches the Fetcher and the Browser: nothing, after a read.
"""

import os

import pytest

from stepout import capabilities, gate
from stepout.capabilities.base import RunContext, RunState
from stepout.capabilities.read_text import ReadText, ReadTextAction
from stepout.domain import AnswerAction, BrowseAction, FetchAction, FilesAction, PlanAction, PlanStep, Refuse, Allow
from stepout.files import Files, Grant
from stepout.model import ModelResponse
from stepout.reader import Reader
from tests.support.pdfs import make_pdf
from tests.test_runner import FakeBrowser, FakeFetcher, Harness, browse, delegate, fetch, say


def norm(p) -> str:
    return os.path.normcase(os.path.realpath(p))


def reads(path):
    return ModelResponse(action=ReadTextAction(path=str(path)), cost_usd=0.001)


def steps(*pairs):
    return ModelResponse(action=PlanAction(steps=[PlanStep(role=role, goal=goal) for role, goal in pairs]), cost_usd=0.001)


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "cv.pdf").write_bytes(make_pdf(["Ana Quinn - Data Engineer"]))
    (d / "scan.pdf").write_bytes(make_pdf([""]))
    (d / "empty.txt").write_text("")
    (d / "binary.txt").write_bytes(b"\x00\x01\x02" * 100)
    (d / ".env").write_text("KEY=not-a-real-key")
    return d


def files_for(folder):
    return Files([Grant(norm(folder), "read")])


# --- the Gate -----------------------------------------------------------------------------------------------------------------


async def _quiet(*args, **kwargs):
    return None


def ctx_with(state):
    return RunContext(run_id="r", role="direct", hands={}, cancelled=lambda: False, emit=_quiet, state=state)


def test_the_gate_refuses_the_web_to_a_tainted_run_and_only_the_web():
    state = RunState()
    web = [FetchAction(url="https://example.com"), BrowseAction(op="open", url="https://example.com")]
    other = [FilesAction(op="list", path="C:\\docs"), ReadTextAction(path="C:\\docs\\a.txt"), AnswerAction(text="done")]
    allowed = frozenset({"fetch", "browse", "files", "read_text", "answer"})
    assert all(isinstance(gate.check(a, allowed, ctx_with(state)), Allow) for a in web + other)  # before a read: everything as before

    state.taint("the contents of cv.pdf were read")
    for action in web:
        verdict = gate.check(action, allowed, ctx_with(state))
        assert isinstance(verdict, Refuse) and "the web is closed for the rest of this task" in verdict.reason
        assert "cv.pdf were read" in verdict.reason and "never be sent out through a URL" in verdict.reason
    assert all(isinstance(gate.check(a, allowed, ctx_with(state)), Allow) for a in other)  # the disk and the answer are not the way out


def test_which_capabilities_reach_the_web_is_declared_and_the_first_reason_is_kept():
    assert {c.name for c in capabilities.ALL if c.reaches_web} == {"web_search", "fetch", "browse"}
    state = RunState()
    state.taint("first")
    state.taint("second")
    assert state.tainted == "first"


# --- only file text taints ----------------------------------------------------------------------------------------------------


async def test_a_read_taints_the_run_but_a_refusal_a_scan_an_empty_file_and_a_binary_do_not(folder):
    cap = ReadText()
    for name in (".env", "scan.pdf", "empty.txt", "binary.txt", "missing.txt"):
        state = RunState()
        await cap.run(ReadTextAction(path=str(folder / name)), RunContext("r", "reader", {"read_text": Reader(files_for(folder))}, lambda: False, _quiet, state))
        assert state.tainted == "", name  # nothing from a file reached the Run
    state = RunState()
    await cap.run(ReadTextAction(path=str(folder / "cv.pdf")), RunContext("r", "reader", {"read_text": Reader(files_for(folder))}, lambda: False, _quiet, state))
    assert state.tainted == f"the contents of {folder / 'cv.pdf'} were read"


# --- through the Runner -------------------------------------------------------------------------------------------------------


async def test_after_a_read_a_fetch_is_refused_the_fetcher_is_never_called_and_search_is_not_offered(tmp_path, folder):
    script = [
        steps(("reader", f"read {folder / 'cv.pdf'}"), ("direct", "look up the company")),  # 0 the Orchestrator plans; the Reader starts
        reads(folder / "cv.pdf"),  # 1
        say("The CV says Ana Quinn is a data engineer."),  # 2
        delegate(1),  # 3
        fetch("https://example.com/company"),  # 4 the Direct agent tries the web after the read
        say("I could not reach the web."),  # 5
        say("Here is what the CV says; I could not look up the company."),  # 6
    ]
    h = Harness(tmp_path, script, files=files_for(folder))
    task = await h.run("summarize my cv and look up the company")

    assert h.fetcher.urls == []  # the request never left
    assert "Refused: the web is closed for the rest of this task" in h.seen_by(5)  # the Direct agent is told why, in words it can act on
    refused = [e for e in h.ledger.query(task.id) if e.kind == "step" and e.data["verdict"] == "refuse"]
    assert len(refused) == 1 and refused[0].role == "direct" and refused[0].data["action"]["kind"] == "fetch"
    # Web search is offered on the plan and on the call that asks for the read (3 left), and on none after the CV's text came back.
    assert [r.max_searches for r in h.model.requests] == [3, 3, 0, 0, 0, 0, 0]
    assert h.replies[0].text.startswith("Here is what the CV says")


async def test_after_a_read_browsing_is_refused_too_whichever_role_holds_it(tmp_path, folder):
    browser = FakeBrowser(("URL: https://example.com/job\nTitle: Job\nText: ...", None))
    script = [steps(("reader", f"read {folder / 'cv.pdf'}"), ("browser", "open the posting")), reads(folder / "cv.pdf"), say("read"), delegate(1), browse("open", "https://example.com/job"), say("blocked"), say("done")]
    h = Harness(tmp_path, script, files=files_for(folder), browser=browser)
    await h.run("compare")
    assert browser.calls == [] and "the web is closed" in h.seen_by(5)  # the Browser agent was never let near a page


async def test_the_web_first_and_the_reading_last_works_as_planned(tmp_path, folder):
    browser = FakeBrowser(("URL: https://example.com/job\nTitle: Job\nText: Wanted: Python", None))
    script = [
        steps(("browser", "read the posting"), ("reader", f"read {folder / 'cv.pdf'}")),
        browse("open", "https://example.com/job"),  # allowed: nothing has been read yet
        say("The posting wants Python."),
        delegate(1),
        reads(folder / "cv.pdf"),
        say("The CV says data engineer."),
        say("Both match."),
    ]
    h = Harness(tmp_path, script, files=files_for(folder), browser=browser)
    task = await h.run("compare my cv to the job posting")
    assert len(browser.calls) == 1 and h.replies[0].text.startswith("Both match")
    assert not [e for e in h.ledger.query(task.id) if e.kind == "step" and e.data["verdict"] == "refuse"]  # nothing was refused


async def test_a_read_that_returns_nothing_leaves_the_web_open(tmp_path, folder):
    script = [
        steps(("reader", f"read {folder / '.env'}"), ("direct", "look something up")),
        reads(folder / ".env"),  # Denied: off-limits
        say("It is blocked."),
        delegate(1),
        fetch("https://example.com/x"),
        say("Found it."),
        say("done"),
    ]
    h = Harness(tmp_path, script, files=files_for(folder), fetcher=FakeFetcher("page text"))
    await h.run("show my .env and look something up")
    assert h.fetcher.urls == ["https://example.com/x"]  # a refused read gave the Run nothing to leak
    assert [r.max_searches for r in h.model.requests][3:] == [3, 3, 3, 3]


async def test_taint_belongs_to_one_run_the_next_task_starts_clean(tmp_path, folder):
    script = [
        steps(("reader", f"read {folder / 'cv.pdf'}")), reads(folder / "cv.pdf"), say("ok"), say("first done"),  # task 1 reads a file
        steps(("direct", "look up")), fetch("https://example.com/y"), say("found"), say("second done"),  # task 2 only uses the web
    ]
    h = Harness(tmp_path, script, files=files_for(folder), fetcher=FakeFetcher("page text"))
    await h.run("read my cv")
    await h.run("now look something up")
    assert h.fetcher.urls == ["https://example.com/y"]


async def test_a_run_that_never_reads_is_unchanged(tmp_path):
    h = Harness(tmp_path, [steps(("direct", "look up")), fetch("https://example.com/z"), say("found"), say("done")])
    await h.run("look something up")
    assert h.fetcher.urls == ["https://example.com/z"] and {r.max_searches for r in h.model.requests} == {3}


def test_a_taint_with_no_reason_still_taints():
    state = RunState()
    state.taint("")
    assert state.tainted
