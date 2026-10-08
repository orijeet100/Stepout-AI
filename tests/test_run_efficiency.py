"""Waste in a Run, measured with the scripted model: a repeat the guard skips, and how many model calls a two-part plan takes.

From the live C2 run: the Browser agent asked for `open <same page>` three more times after a click and two `more`. The guard did stop the page
loading again, but it recorded each as an allowed step, and the model asked because the first view had shrunk out of its notes.
"""

from tests.test_runner import FakeBrowser, Harness, browse, plan, say

URL = "https://jobs.example.com/data-engineer"


def page(n):
    return (f"URL: {URL}\nTitle: Data Engineer\nText: part {n}", None)


def browser_steps(h, task):
    return [e for e in h.ledger.query(task.id) if e.kind == "step" and e.role == "browser"]


async def test_a_repeat_whose_result_is_still_in_the_notes_is_skipped_and_recorded_as_one(tmp_path):
    browser = FakeBrowser(page(1))
    h = Harness(tmp_path, [plan("read the posting", role="browser"), browse("open", URL), browse("open", URL), say("It asks for Python."), say("Python.")], browser=browser)
    task = await h.run("what does it ask for?")

    assert [c[1] for c in browser.calls] == ["open"]  # loaded once
    first, repeat, _ = browser_steps(h, task)
    assert "repeat" not in first.data and repeat.data["repeat"] is True and repeat.data["summary"].startswith("repeat, not run again: browse open")
    assert repeat.data["verdict"] == "allow"  # the Gate had nothing against it; it was just not needed
    assert "already ran exactly this" in h.seen_by(3)


async def test_a_page_that_has_shrunk_out_of_the_notes_may_be_opened_again(tmp_path):
    browser = FakeBrowser(page(1), page(2), page(3), page(4), page(5))
    script = [
        plan("read the posting", role="browser"),
        browse("open", URL), browse("click", link=30), browse("more"), browse("more"),  # by now the first view is a one-line stub
        browse("open", URL),  # the model wants the posting back: that is not a repeat of anything it can still read
        say("Python, SQL."), say("It asks for Python and SQL."),
    ]
    h = Harness(tmp_path, script, browser=browser)
    task = await h.run("what does it ask for?")

    assert [c[1] for c in browser.calls] == ["open", "click", "more", "more", "open"]
    assert "(earlier page)" in h.seen_by(5) and "Text: part 5" in h.seen_by(6)  # it had shrunk when asked, and it is whole again after
    assert not any(e.data.get("repeat") for e in browser_steps(h, task))


async def test_an_open_after_a_click_is_run_even_though_the_old_view_is_still_in_the_notes(tmp_path):
    """Open a list, click into a listing, open the list again: the browser is on the listing now, so the list's link numbers would point into the
    wrong page. The old view is still readable (two stay in full), but this is not a repeat of anything that can still be trusted."""
    browser = FakeBrowser(page(1), page(2), page(3))
    h = Harness(tmp_path, [plan("read", role="browser"), browse("open", URL), browse("click", link=3), browse("open", URL), say("ok"), say("ok")], browser=browser)
    task = await h.run("x")

    assert [c[1] for c in browser.calls] == ["open", "click", "open"]
    assert not any(e.data.get("repeat") for e in browser_steps(h, task))


async def test_a_files_repeat_is_still_skipped_after_other_calls_because_its_result_does_not_depend_on_them(tmp_path):
    from tests.test_runner import FakeFiles, looks

    files = FakeFiles("a, b")
    h = Harness(tmp_path, [plan("look", role="files"), looks("list", "D:\\A"), looks("list", "D:\\B"), looks("list", "D:\\A"), say("ok"), say("ok")], files=files)
    await h.run("x")
    assert [c[1] for c in files.calls] == ["D:\\A", "D:\\B"]
