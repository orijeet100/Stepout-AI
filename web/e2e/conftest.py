"""End-to-end fixtures: a real Chrome drives the built page (vite preview) against the mock backend.

Run:  python -m pytest web/e2e -q      (the Main lane's pytest only collects tests/, so these do not mix with its run)
Needs: `npm install` in web/ and the installed Chrome. Everything runs on free ports and is stopped afterwards; saved
screenshots go to pytest's tmp dir, never into git.
"""

from __future__ import annotations

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


@pytest.fixture
def page(browser, stack):
    ctx = browser.new_context(viewport={"width": 1100, "height": 760})
    page = ctx.new_page()
    page.console_errors = []
    page.on("console", lambda m: page.console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page.console_errors.append(str(e)))
    page.goto(stack[0])
    page.wait_for_selector(".chat")  # the chat list has loaded: the socket is up
    yield page
    assert page.console_errors == [], page.console_errors
    ctx.close()
