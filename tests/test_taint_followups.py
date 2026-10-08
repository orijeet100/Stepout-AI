"""Taint across follow-ups: a Run that builds on an answer which used the User's files starts with the web closed, and the closing is remembered.

Same rule as a single Run (tests/test_taint.py), carried through the chat: the Run that read a file saves `runs.tainted`, `history.exchanges` marks
its Exchange, and a Run that is given that Exchange (the front door linked it, or its fail-open fallback did) is tainted from its first step.
A new task the front door did not link to it is not. The real app loop, Store, Reader and Gate; a scripted model.
"""

import os

from stepout import history
from stepout.capabilities.read_text import ReadTextAction
from stepout.domain import Exchange, Proceed, Task
from stepout.files import Files, Grant
from stepout.model import ModelResponse
from stepout.runner import _previous_block
from tests.support.pdfs import make_pdf
from tests.support.screeners import FixedScreener
from tests.test_history import ask, serve
from tests.test_runner import FakeBrowser, Harness, browse, plan, say

URL = "https://example.com/about"
PAGE = (f"URL: {URL}\nTitle: About\nText: Example Corp builds anvils.", None)


def x(n, tainted):
    return Exchange(id=n, request=f"request {n}", reply=f"reply {n}", did="", tainted=tainted, run_id=f"r{n}")


def reads(path):
    return ModelResponse(action=ReadTextAction(path=str(path)), cost_usd=0.001)


async def follow_up(h, previous):
    await h.runner.submit(Task(user_id="u", request="and open the company site"), previous=previous)


def refusals(h, task_request="and open the company site"):
    return [e for e in h.ledger.query(next(t for t in h.traced if t.kind == "step").task_id) if e.kind == "step" and e.data["verdict"] == "refuse"]


# --- the Runner -----------------------------------------------------------------------------------------------------------------


async def test_a_run_given_a_tainted_exchange_has_the_web_closed_from_its_first_step(tmp_path):
    browser = FakeBrowser(PAGE)
    h = Harness(tmp_path, [plan("open the site", role="browser"), browse("open", URL), say("I could not open it."), say("The web is closed for this one.")], browser=browser)
    await follow_up(h, [x(1, tainted=True)])

    assert browser.calls == []  # the page was never opened
    (refused,) = refusals(h)
    assert refused.data["action"]["kind"] == "browse" and "an earlier answer it builds on (#1) used the contents of your files" in refused.data["summary"]
    assert all(r.max_searches == 0 for r in h.model.requests)  # and web search is not offered either


async def test_a_run_given_only_untainted_exchanges_is_not_tainted(tmp_path):
    browser = FakeBrowser(PAGE)
    h = Harness(tmp_path, [plan("open the site", role="browser"), browse("open", URL), say("Example Corp builds anvils."), say("Done.")], browser=browser)
    await follow_up(h, [x(1, tainted=False), x(2, tainted=False)])

    assert [c[1:3] for c in browser.calls] == [("open", URL)] and refusals(h) == []
    assert h.model.requests[0].max_searches > 0


async def test_the_orchestrator_is_told_which_earlier_answers_used_the_users_files():
    block = _previous_block([x(1, tainted=False), x(2, tainted=True)])
    first, second = block.split("\n\n#2")
    assert "files" not in first.replace("request 1", "")  # an ordinary exchange reads as before
    assert "used the contents of your files" in second and "the web is closed" in second


# --- through the saved chat -------------------------------------------------------------------------------------------------------


async def test_follow_ups_inherit_the_taint_through_the_chat_and_unlinked_tasks_do_not(tmp_path):
    folder = tmp_path / "Docs"
    folder.mkdir()
    cv = folder / "cv.pdf"
    cv.write_bytes(make_pdf(["Ana Quinn - Data Engineer at Example Corp"]))
    browser = FakeBrowser(PAGE)
    messages = [
        ask("c1", f"Summarize {cv}"),  # 1 reads the file
        ask("c1", "and open the company site"),  # 2 builds on 1
        ask("c1", "what is on example.com/about?"),  # 3 a new task: the front door links nothing
        ask("c1", "and who else works there?"),  # 4 builds on 2, which only inherited the taint
    ]
    script = [
        plan(f"read {cv}", role="reader"), reads(cv), say("Ana is a data engineer at Example Corp."), say("She is a data engineer."),
        plan("open the site", role="browser"), browse("open", URL), say("I could not open it."), say("The web is closed after reading your file."),
        plan("open the page", role="browser"), browse("open", URL), say("Example Corp builds anvils."), say("It builds anvils."),
        plan("search for staff", role="browser"), browse("open", URL), say("I could not open it."), say("Still closed."),
    ]
    screener = FixedScreener((Proceed(), 0.0), (Proceed(related=[1]), 0.0), (Proceed(), 0.0), (Proceed(related=[2]), 0.0))
    store = await serve(tmp_path, messages, script, screener, files=Files([Grant(os.path.normcase(os.path.realpath(folder)), "read")]), browser=browser)

    assert [c[1:3] for c in browser.calls] == [("open", URL)]  # only the unlinked task (3) reached the web
    xs = history.exchanges(store, "c1")
    assert [x.tainted for x in xs] == [True, True, False, True]  # read it; built on it; unrelated; built on the one that built on it
    runs = store.query("SELECT tainted FROM runs ORDER BY started_at")
    assert [bool(r["tainted"]) for r in runs] == [True, True, False, True]
    assert history.exchanges(store, "elsewhere") == []


async def test_the_fail_open_fallback_carries_taint_too(tmp_path):
    """If the front door cannot answer, the last three Exchanges go with the message: a tainted one among them closes the web."""
    folder = tmp_path / "Docs"
    folder.mkdir()
    cv = folder / "cv.pdf"
    cv.write_bytes(make_pdf(["Ana Quinn - Data Engineer"]))
    browser = FakeBrowser(PAGE)
    messages = [ask("c1", f"Summarize {cv}"), ask("c1", "open the company site")]
    script = [
        plan(f"read {cv}", role="reader"), reads(cv), say("A data engineer."), say("Ana is a data engineer."),
        plan("open the site", role="browser"), browse("open", URL), say("I could not open it."), say("Closed."),
    ]
    screener = FixedScreener((Proceed(), 0.0), RuntimeError("the front door is down"))
    store = await serve(tmp_path, messages, script, screener, files=Files([Grant(os.path.normcase(os.path.realpath(folder)), "read")]), browser=browser)

    assert browser.calls == []
    assert [x.tainted for x in history.exchanges(store, "c1")] == [True, True]


async def test_a_run_that_fails_after_reading_a_file_still_saves_that_it_was_tainted(tmp_path):
    """The model call after the read raises (the script has run out): the Run ends `failed`, and what it read is not forgotten."""
    import pytest

    folder = tmp_path / "Docs"
    folder.mkdir()
    cv = folder / "cv.pdf"
    cv.write_bytes(make_pdf(["Ana Quinn - Data Engineer"]))
    h = Harness(tmp_path, [plan(f"read {cv}", role="reader"), reads(cv)], files=Files([Grant(os.path.normcase(os.path.realpath(folder)), "read")]))
    with pytest.raises(IndexError):
        await h.run(f"Summarize {cv}")
    (run,) = h.store.query("SELECT outcome, tainted FROM runs")
    assert run["outcome"] == "failed" and run["tainted"]
