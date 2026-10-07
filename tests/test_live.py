"""Live smoke tests: the whole loop against the real API, real Chrome and the real disk.

They cost a few cents, so the default run skips them: `pytest -m eval -s tests/test_live.py`.
Each task is simple on purpose and asserts a fact the model cannot guess, so a pass means the
loop (plan, delegate, hands, report) really works. `-s` prints calls and cost per task.
"""

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

from stepout.browser import Browser
from stepout.domain import Task
from stepout.fetch import Fetcher
from stepout.files import Files, Grant
from stepout.ledger import Ledger
from stepout.model import AnthropicModel
from stepout.runner import Runner
from stepout.store import Store

load_dotenv()
pytestmark = [pytest.mark.eval, pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")]


@pytest.fixture
def folder(tmp_path):
    """3 PDFs and 2 text files: a count the model cannot guess."""
    d = tmp_path / "stuff"
    d.mkdir()
    for name in ("a.pdf", "b.pdf", "c.pdf", "x.txt", "y.txt"):
        (d / name).write_text(name)
    return d


async def ask(tmp_path, request, folder=None):
    ledger = Ledger(Store(tmp_path / "live.db"))
    replies = []

    async def notify(reply):
        replies.append(reply.text)

    files = Files([Grant(os.path.normcase(os.path.realpath(folder)), "read")]) if folder else None
    browser = Browser(shots=tmp_path / "shots")
    runner = Runner(AnthropicModel(), Fetcher(), ledger, notify, files=files, browser=browser)
    task = Task(user_id="live", request=request, route="answer")
    try:
        await runner.submit(task)
    finally:
        await browser.aclose()
    events = ledger.query(task.id)
    steps = [e for e in events if e.kind == "step"]
    roles = {e.role for e in steps}
    print(f"\n  {request[:58]!r}\n    -> {len(steps)} model calls, ${sum(e.cost_usd for e in events):.4f}, roles {sorted(roles)}")
    for e in steps:
        print(f"       {e.role:13} ${e.cost_usd:.4f}  {e.data['summary'][:95]}")
    return replies[0], events, roles


async def test_a_trivial_question_costs_one_call(tmp_path):
    reply, events, roles = await ask(tmp_path, "What is 17 times 3? Reply with just the number.")
    assert "51" in reply and roles == {"orchestrator"}
    assert len([e for e in events if e.kind == "step"]) == 1


async def test_a_web_question_goes_through_the_direct_agent_with_a_source(tmp_path):
    reply, _, roles = await ask(tmp_path, "Using a web search, what is the current stable version of Python? Give one source link.")
    assert re.search(r"3\.\d+", reply) and "http" in reply and "direct" in roles


async def test_counting_files_goes_through_the_files_agent(tmp_path, folder):
    reply, _, roles = await ask(tmp_path, f"How many files are in {folder}, by file type? Give the counts.", folder)
    assert "3" in reply and "2" in reply and ".pdf" in reply.lower() and "files" in roles


async def test_reading_a_page_goes_through_the_browser_agent_and_leaves_a_screenshot(tmp_path):
    reply, events, roles = await ask(tmp_path, "Open https://example.com and tell me the main heading on the page.")
    assert "Example Domain" in reply and "browser" in roles
    shot = next(e for e in events if e.kind == "shot")
    assert (tmp_path / "shots" / shot.data["shot"]).stat().st_size > 1000


async def test_one_task_can_need_two_agents(tmp_path, folder):
    reply, _, roles = await ask(tmp_path, f"Two things: open https://example.com and tell me its main heading; and tell me how many files are in {folder}.", folder)
    assert "Example Domain" in reply and "5" in reply and {"browser", "files"} <= roles


async def test_a_protected_file_is_refused_and_its_contents_never_appear(tmp_path):
    secret = Path(__file__).resolve().parents[1] / ".env"
    reply, _, _ = await ask(tmp_path, f"Show me what is inside {secret}")
    assert "sk-ant" not in reply and "blocked" in reply.lower()
