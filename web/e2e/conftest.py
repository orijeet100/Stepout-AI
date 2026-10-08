"""End-to-end fixtures: a real Chrome drives the built page (vite preview) against the mock backend.

Run:  python -m pytest web/e2e -q      (the Main lane's pytest only collects tests/, so these do not mix with its run)
Needs: `npm install` in web/ and the installed Chrome. Everything runs on free ports and is stopped afterwards; saved
screenshots go to pytest's tmp dir, never into git.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url: str, seconds: float = 30) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"{url} did not come up")


def wait_until_idle(mock_url: str, seconds: float = 90) -> None:
    """The mock is shared by every flow and keeps replaying a Run a flow walked away from: start each flow on an idle one."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        with urllib.request.urlopen(f"{mock_url}/api/conversations", timeout=2) as r:
            if all(chat["state"] == "idle" for chat in json.loads(r.read())):
                return
        time.sleep(0.25)
    raise RuntimeError("the mock did not go idle")


def stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":  # kill the whole tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def stack():
    """(page url, mock url): the mock replays fixtures at 0.3x the recorded gaps, the page is a production build behind vite preview."""
    node, npm = shutil.which("node"), shutil.which("npm")
    assert node and npm, "node and npm are needed to build the page"
    subprocess.run([npm, "run", "build"], cwd=WEB, check=True, capture_output=True)
    mock_port, page_port = free_port(), free_port()
    mock = subprocess.Popen([sys.executable, str(WEB / "mock" / "server.py"), "--port", str(mock_port), "--speed", "0.3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = {**os.environ, "VITE_BACKEND": f"http://127.0.0.1:{mock_port}"}
    preview = subprocess.Popen([node, str(WEB / "node_modules" / "vite" / "bin" / "vite.js"), "preview", "--host", "127.0.0.1", "--port", str(page_port), "--strictPort"], cwd=WEB, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(f"http://127.0.0.1:{mock_port}/api/conversations")
        wait_for(f"http://127.0.0.1:{page_port}/")
        yield f"http://127.0.0.1:{page_port}", f"http://127.0.0.1:{mock_port}"
    finally:
        stop(preview)
        stop(mock)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        chrome = pw.chromium.launch(channel="chrome", headless=True)  # the installed Chrome, like the Browser agent
        yield chrome
        chrome.close()


def guarded(browser, url: str):
    """A page that fails its flow on a console error or an HTTP error the flow did not provoke."""
    ctx = browser.new_context(viewport={"width": 1100, "height": 760})
    page = ctx.new_page()
    page.console_errors = []
    page.bad_responses = []  # every HTTP answer of 400 or more: a flow that provokes one on purpose removes it itself
    page.on("console", lambda m: page.console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page.console_errors.append(str(e)))
    page.on("response", lambda r: page.bad_responses.append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)
    page.goto(url)
    page.wait_for_selector(".banner", state="detached")  # connected: no "Connecting…" any more
    page.wait_for_selector(".chat, .side__empty")  # and the chat list is there (or says there are none)
    yield page
    assert not page.console_errors and not page.bad_responses, f"console errors {page.console_errors}; requests that failed and the flow did not provoke {page.bad_responses}"
    ctx.close()


@pytest.fixture
def page(browser, stack):
    wait_until_idle(stack[1])
    yield from guarded(browser, stack[0])


@pytest.fixture(scope="session")
def real_stack(stack, tmp_path_factory):
    """The page served by the real backend (the wiring of `python -m stepout.app web`) with a scripted model and an empty database:
    what the page reads back after a restart is the API's own answer, not the mock's. `stack` builds the page first."""
    port = free_port()
    db = tmp_path_factory.mktemp("real-backend") / "chats.db"
    proc = subprocess.Popen([sys.executable, str(WEB / "mock" / "real_backend.py"), "--port", str(port), "--db", str(db), "--delay", "0.15"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(f"http://127.0.0.1:{port}/api/conversations")
        yield f"http://127.0.0.1:{port}"
    finally:
        stop(proc)


@pytest.fixture
def real_page(browser, real_stack):
    yield from guarded(browser, real_stack)
