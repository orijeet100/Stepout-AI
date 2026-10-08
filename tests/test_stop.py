"""Stop: pressed during a long model call, a long read, a long walk or a slow page load, it ends the Run within a moment and leaves the row `stopped`.

Before, the Runner looked at the Stop flag only between steps, so a hand that took 30 s (a big PDF, a slow page, a deep walk) or a model call that took
20 s made the button wait for it. The Runner now stops waiting for whatever it is awaiting the moment the flag is set.
"""

import asyncio
import os
import time

import pytest

from stepout.capabilities.read_text import ReadTextAction
from stepout.domain import FilesAction
from stepout.model import ModelResponse, ModelRequest
from tests.test_runner import FakeBrowser, FakeFiles, Harness, browse, looks, plan

SLOW = 30  # seconds: far longer than any test waits, so finishing quickly can only mean it was cut short
BUDGET = 3.0  # seconds from pressing Stop to the Run being over (it takes well under one)


async def press_stop_during(h, cancel, request="do it", after=0.3):
    """Start the Run, press Stop `after` seconds in, and return how long the Run took to end after that."""
    task = asyncio.create_task(h.run(request))
    await asyncio.sleep(after)
    pressed = time.perf_counter()
    cancel.set()
    await asyncio.wait_for(task, SLOW)
    return time.perf_counter() - pressed


def outcome(h):
    return [r["outcome"] for r in h.store.query("SELECT outcome FROM runs")]


def stopped_reply(h):
    assert len(h.replies) == 1 and h.replies[0].text == "Stopped by you."


class Sleeper:
    """A hand that takes SLOW seconds and does not look at the Stop flag at all (a thread in a PDF parser, a page that will not load)."""

    def __init__(self):
        self.started = asyncio.Event()

    async def run(self, *args, **kwargs):
        self.started.set()
        await asyncio.sleep(SLOW)
        return "too late"

    async def read(self, *args, **kwargs):
        return await self.run()

    async def close(self, run_id):
        pass


async def test_stop_during_a_long_read_ends_the_run_within_a_moment(tmp_path):
    cancel = asyncio.Event()
    h = Harness(tmp_path, [plan("read it", role="reader"), ModelResponse(action=ReadTextAction(path="D:\\Docs\\big.pdf"), cost_usd=0.001)], cancel=cancel)
    h.runner._hands["read_text"] = Sleeper()
    took = await press_stop_during(h, cancel)
    assert took < BUDGET, took
    stopped_reply(h)
    assert outcome(h) == ["cancelled"]  # the contract's `stopped`


async def test_stop_during_a_long_walk_ends_the_run_within_a_moment(tmp_path):
    cancel = asyncio.Event()
    h = Harness(tmp_path, [plan("count them", role="files"), ModelResponse(action=FilesAction(op="count", path="D:\\", pattern=None), cost_usd=0.001)], cancel=cancel, files=Sleeper())
    took = await press_stop_during(h, cancel)
    assert took < BUDGET, took
    stopped_reply(h)
    assert outcome(h) == ["cancelled"]


async def test_stop_during_a_slow_page_load_ends_the_run_and_closes_the_browser_session(tmp_path):
    cancel = asyncio.Event()
    browser = FakeBrowser()
    sleeper = Sleeper()
    browser.run = sleeper.run  # a page that will not load
    h = Harness(tmp_path, [plan("open it", role="browser"), browse("open", "https://slow.example/")], cancel=cancel, browser=browser)
    took = await press_stop_during(h, cancel)
    assert took < BUDGET, took
    stopped_reply(h)
    assert outcome(h) == ["cancelled"] and len(browser.closed) == 1  # the page it was loading goes with the Run


async def test_stop_during_a_long_model_call_ends_the_run_within_a_moment(tmp_path):
    cancel = asyncio.Event()
    h = Harness(tmp_path, [], cancel=cancel)

    async def slow_call(request: ModelRequest):
        await asyncio.sleep(SLOW)  # a long search
        return ModelResponse(action=plan("x").action, cost_usd=0.001)

    h.model.call = slow_call
    took = await press_stop_during(h, cancel)
    assert took < BUDGET, took
    stopped_reply(h)
    assert outcome(h) == ["cancelled"]


async def test_a_hand_that_does_honour_stop_still_ends_the_run_stopped_not_failed(tmp_path):
    cancel = asyncio.Event()

    class Walker(FakeFiles):
        async def run(self, op, path, pattern=None, cancelled=lambda: False):
            while not cancelled():  # a walk that looks at the flag between directories, as the real one does
                await asyncio.sleep(0.02)
            return "Stopped: you pressed Stop, so this count is partial."

    h = Harness(tmp_path, [plan("count", role="files"), looks("count", "D:\\"), ModelResponse(action=plan("x").action, cost_usd=0.0)], cancel=cancel, files=Walker())
    took = await press_stop_during(h, cancel)
    assert took < BUDGET, took
    assert outcome(h) == ["cancelled"] and h.replies[0].text == "Stopped by you."


async def test_the_real_reader_in_its_thread_is_abandoned_at_once_on_stop(tmp_path, monkeypatch):
    """The real Reader hand and its worker thread: the thread cannot be killed, but the Run must not wait for it."""
    import stepout.reader as reader_mod

    cancel = asyncio.Event()
    h = Harness(tmp_path, [plan("read it", role="reader"), ModelResponse(action=ReadTextAction(path="D:\\Docs\\big.pdf"), cost_usd=0.001)], cancel=cancel)
    monkeypatch.setattr(reader_mod.Reader, "_read", lambda self, path, usage: time.sleep(1.5))  # in the thread, as the real one is
    took = await press_stop_during(h, cancel)
    assert took < 1.0, took  # not the 1.5 s the thread keeps running
    assert outcome(h) == ["cancelled"]


@pytest.mark.skipif(not os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), reason="needs Chrome")
async def test_stop_during_a_real_page_load_in_real_chrome_ends_the_run_and_closes_chrome_s_page(tmp_path):
    """A page that answers after 30 s, a real headless Chrome: Stop must not wait for the page, and the Run's browser context must close promptly."""
    from aiohttp import web

    from stepout.browser import Browser

    release = asyncio.Event()

    async def slow(request):
        await release.wait()  # a page that does not answer until the test lets it
        return web.Response(text="<title>late</title>", content_type="text/html")

    app = web.Application()
    app.router.add_get("/", slow)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}/"
    browser = Browser(policy=lambda u: None)  # the local test page is not on the public web
    cancel = asyncio.Event()
    h = Harness(tmp_path, [plan("open it", role="browser"), browse("open", url)], cancel=cancel, browser=browser)
    try:
        took = await press_stop_during(h, cancel, after=2.5)  # Chrome starts first, then the load begins
        assert took < 5.0, took
        stopped_reply(h)
        assert outcome(h) == ["cancelled"] and browser._sessions == {}  # the Run's context is closed
    finally:
        release.set()
        await browser.aclose()
        await runner.cleanup()
