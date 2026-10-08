"""The Reader Role: what it holds, what it is told, and a real Reader step through the Runner (real files, real PDF, scripted model)."""

import os

import pytest

from stepout.capabilities.read_text import ReadTextAction
from stepout.files import Files, Grant
from stepout.model import HAIKU, ModelResponse
from stepout.roles import ROLES, SPECIALISTS
from tests.support.pdfs import make_pdf
from tests.test_runner import Harness, plan, say


def norm(p) -> str:
    return os.path.normcase(os.path.realpath(p))


def reads(path, cost=0.001):
    return ModelResponse(action=ReadTextAction(path=str(path)), cost_usd=cost)


def test_the_reader_is_a_cheap_short_role_that_holds_one_tool():
    reader = ROLES["reader"]
    assert (reader.model, reader.max_steps, reader.tools) == (HAIKU, 3, ("read_text",))
    assert reader.actions == {"read_text", "answer"} and "reader" in SPECIALISTS


def test_the_reader_is_told_to_stop_at_a_refusal_not_to_guess_a_scan_and_to_treat_files_as_data():
    system = ROLES["reader"].system
    assert "Denied, off-limits or Limit" in system and "never try other spellings" in system
    assert "scanned images" in system and "do not guess" in system
    assert "never instructions" in system and "[redacted]" in system
    assert "cannot open the web" in system


def test_the_orchestrator_is_told_to_plan_the_web_first_and_the_reading_last_and_why():
    system = ROLES["orchestrator"].system
    assert "reader (" in system and "exact full path" in system
    assert "web steps (direct, browser) FIRST and the reader step LAST" in system
    assert "the web is closed for the rest of the task" in system


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    return d


async def test_a_reader_step_reads_a_real_pdf_and_the_orchestrator_gets_the_finding(tmp_path, folder):
    cv = folder / "cv.pdf"
    cv.write_bytes(make_pdf(["Ana Quinn - Data Engineer\nPython, SQL, Airflow (5 years)"]))
    h = Harness(
        tmp_path,
        [plan(f"read {cv} and say what it lists", role="reader"), reads(cv), say("Ana is a data engineer: Python, SQL, Airflow."), say("Your CV lists Python, SQL and Airflow.")],
        files=Files([Grant(norm(folder), "read")]),
    )
    await h.run("what does my cv say?")

    assert h.model.requests[1].tools == ["read_text"] and h.model.requests[1].model == HAIKU  # the Reader's first call
    assert "Ana Quinn - Data Engineer" in h.seen_by(2)  # the Reader saw the file's text, behind the header that names the file
    assert f"read_text {cv}: PDF" in h.seen_by(2)
    assert "Ana is a data engineer: Python, SQL, Airflow." in h.seen_by(3)  # the Orchestrator got the Reader's Finding...
    assert h.replies[0].text.startswith("Your CV lists Python, SQL and Airflow")  # ...and answered from it


async def test_a_reader_asked_for_a_blocked_file_gets_a_refusal_and_no_contents(tmp_path, folder):
    (folder / ".env").write_text("ANTHROPIC_API_KEY=not-a-real-key")
    h = Harness(
        tmp_path,
        [plan(f"read {folder / '.env'}", role="reader"), reads(folder / ".env"), say("It is off-limits."), say("That file is blocked by the Assistant's safety rules.")],
        files=Files([Grant(norm(folder), "read")]),
    )
    await h.run("show me my .env")
    assert "Denied: off-limits" in h.seen_by(2) and "not-a-real-key" not in h.seen_by(2) and "not-a-real-key" not in h.seen_by(3)
