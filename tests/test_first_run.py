"""The first minutes on a machine that is not set up: no key, no grants file, no Chrome, a Chrome that died.

Each must say what is missing and how to fix it, in a line, at the start or at first use: not crash, not hang, not blame a safety rule.
"""

import os
from types import SimpleNamespace

import pytest
from aiohttp import web
from playwright.async_api import Error as PlaywrightError

from stepout import app
from stepout.browser import Browser
from stepout.failure import Failure
from stepout.files import Files
from stepout.roles import ROLES
from tests.test_runner import Harness, browse, plan

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
NOT_FOUND = "BrowserType.launch: Chromium distribution 'chrome' is not found at C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\nRun \"playwright install chrome\""


# --- at start ---------------------------------------------------------------------------------------------------------------------


def test_the_start_up_notes_say_what_is_missing_and_how_to_fix_it(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    key, grants = app.startup_notes()
    assert "ANTHROPIC_API_KEY" in key and "stepout init" in key and "restart" in key
    assert "stepout grant" in grants

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    (tmp_path / "grants.toml").write_text("")
    assert app.startup_notes() == []  # nothing to say when it is set up


# --- at first use -----------------------------------------------------------------------------------------------------------------


def test_with_no_grants_the_files_agent_is_told_how_to_set_them_up_not_that_a_safety_rule_blocks_it(tmp_path):
    import asyncio

    reply = asyncio.run(Files().run("list", str(tmp_path)))
    assert reply.startswith("Denied") and "outside every grant" in reply  # the old wording, still
    assert "stepout grant" in reply and "only the User can" in reply
    assert "safety rule" not in reply and "workaround" not in reply  # this is setup, not a prohibition


def test_the_orchestrator_is_told_to_pass_on_a_setup_instruction_instead_of_calling_it_a_safety_rule():
    assert "no folders are allowed yet" in ROLES["orchestrator"].system


class NoChrome:
    """Playwright on a machine without Chrome: starting works, launching the `chrome` channel does not."""

    async def start(self):
        return self

    @property
    def chromium(self):
        return self

    async def launch(self, **kwargs):
        raise PlaywrightError(NOT_FOUND)


async def test_a_browse_step_without_chrome_fails_the_run_with_one_plain_line(tmp_path, monkeypatch):
    monkeypatch.setattr("stepout.browser.async_playwright", lambda: NoChrome())
    h = Harness(tmp_path, [plan("open it", role="web_browsing"), browse("open", "https://example.com")], browser=Browser())
    task = await h.run("open example.com")

    (reply,) = h.replies
    assert reply.text == "Neither Google Chrome nor Microsoft Edge is installed. Install one of them, then try again."
    (error,) = [e for e in h.ledger.query(task.id) if e.kind == "error"]
    assert error.data["cause"] == "chrome" and error.role == "web_browsing" and error.data["type"] == "Failure"
    (run,) = h.store.query("SELECT outcome FROM runs")
    assert run["outcome"] == "failed"
    assert len(h.model.requests) == 2  # it did not spend eight steps trying a dead browser


class Installed:
    """Playwright with only the given channels installed: launching any other says it is not found, and records what was asked."""

    def __init__(self, *channels):
        self.channels, self.asked = channels, []

    async def start(self):
        return self

    @property
    def chromium(self):
        return self

    async def launch(self, channel=None, **kwargs):
        self.asked.append(channel)
        if channel not in self.channels:
            raise PlaywrightError(NOT_FOUND.replace("'chrome'", f"'{channel}'"))
        return SimpleNamespace(channel=channel)


async def test_without_chrome_the_browser_falls_back_to_edge(monkeypatch):
    launcher = Installed("msedge")
    monkeypatch.setattr("stepout.browser.async_playwright", lambda: launcher)
    browser = Browser()
    await browser._start_chrome()
    assert launcher.asked == ["chrome", "msedge"] and browser._chrome.channel == "msedge"


async def test_without_chrome_or_edge_the_failure_names_both(monkeypatch):
    monkeypatch.setattr("stepout.browser.async_playwright", lambda: Installed())
    with pytest.raises(Failure) as caught:
        await Browser()._start_chrome()
    assert "Google Chrome" in caught.value.message and "Microsoft Edge" in caught.value.message


async def test_chrome_that_cannot_start_for_another_reason_says_so_in_a_line(tmp_path, monkeypatch):
    class Broken(NoChrome):
        async def launch(self, **kwargs):
            raise PlaywrightError("BrowserType.launch: Browser closed unexpectedly\nstack stack stack")

    monkeypatch.setattr("stepout.browser.async_playwright", lambda: Broken())
    h = Harness(tmp_path, [plan("open it", role="web_browsing"), browse("open", "https://example.com")], browser=Browser())
    await h.run("open example.com")
    (reply,) = h.replies
    assert reply.text.startswith("The browser could not be started (BrowserType.launch: Browser closed unexpectedly)") and "stack" not in reply.text


@pytest.mark.skipif(not os.path.exists(CHROME), reason="needs Chrome")
async def test_a_chrome_that_died_is_started_again_for_the_next_run():
    page = web.Application()
    async def home(request):
        return web.Response(text="<title>Home</title><h1>Welcome</h1>", content_type="text/html")

    page.router.add_get("/", home)
    runner = web.AppRunner(page)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    url = f"http://127.0.0.1:{runner.addresses[0][1]}/"
    browser = Browser(policy=lambda u: None)  # the local test page is not on the public web
    try:
        first, _ = await browser.run("r1", "open", url)
        assert "Welcome" in first
        await browser._chrome.close()  # Chrome dies (killed, crashed) between two Runs
        second, _ = await browser.run("r2", "open", url)
        assert "Welcome" in second, second  # a new Chrome, not "could not load the page" for ever
    finally:
        await browser.aclose()
        await runner.cleanup()
