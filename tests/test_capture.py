"""Capture: off by default, one line per model call when on, never for a Run that has read a file, redacted, and gone with its chat."""

import json

from stepout.capture import Capture, from_env
from stepout.domain import Exchange
from stepout.access.files import Files, Grant
from stepout.model import AnswerAction, ModelRequest, ModelResponse
from tests.support.pdfs import make_pdf
from tests.test_reader_role import norm, reads
from tests.test_runner import FakeFetcher, Harness, fetch, plan, say


def lines(folder, run_id):
    return [json.loads(line) for line in (folder / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()]


def only_run(h, task):
    return h.ledger.query(task.id)[0].run_id


def test_it_is_on_only_when_asked_for(tmp_path):
    assert from_env(tmp_path, {}) is None and from_env(tmp_path, {"STEPOUT_CAPTURE": "0"}) is None
    assert isinstance(from_env(tmp_path, {"STEPOUT_CAPTURE": "1"}), Capture)


async def test_each_model_call_of_a_run_is_one_line(tmp_path):
    folder = tmp_path / "capture"
    h = Harness(tmp_path, [plan("find it"), fetch("https://example.com/p"), say("found"), say("done")], fetcher=FakeFetcher("page text"))
    h.runner._capture = Capture(folder)
    task = await h.run("what is on example.com?")

    got = lines(folder, only_run(h, task))
    assert [g["role"] for g in got] == ["orchestrator", "web_research", "web_research", "orchestrator"]
    assert got[0]["sent"] == "Task: what is on example.com?" and '"kind": "plan"' in got[0]["received"]
    assert "page text" in got[2]["sent"]  # the page's text is in the next prompt, as it was sent
    assert all(g["model"] and "cost_usd" in g and "duration_ms" in g for g in got)


async def test_a_secret_looking_value_is_redacted_in_the_file(tmp_path):
    folder = tmp_path / "capture"
    h = Harness(tmp_path, [say("your key sk-ant-api03-abcdefghijklmnopqrstuvwx is noted")])
    h.runner._capture = Capture(folder)
    task = await h.run("my password: hunter2, remember it")
    (got,) = lines(folder, only_run(h, task))
    assert "hunter2" not in got["sent"] and "[redacted]" in got["sent"]
    assert "sk-ant-api03" not in got["received"]


async def test_nothing_is_written_once_a_file_has_been_read(tmp_path):
    folder = tmp_path / "capture"
    docs = tmp_path / "docs"
    docs.mkdir()
    cv = docs / "cv.pdf"
    cv.write_bytes(make_pdf(["Ana Quinn - Data Engineer, a private line"]))
    h = Harness(
        tmp_path,
        [plan(f"read {cv}", role="local_file_reader"), reads(cv), say("A data engineer."), say("Your CV says you are a data engineer.")],
        files=Files([Grant(norm(docs), "read")]),
    )
    h.runner._capture = Capture(folder)
    task = await h.run("what does my cv say?")

    got = lines(folder, only_run(h, task))
    assert [g["role"] for g in got] == ["orchestrator", "local_file_reader"]  # the plan, and the call that asked to read; the calls after the read are not kept
    assert "Ana Quinn" not in "".join(json.dumps(g) for g in got)


async def test_a_run_that_builds_on_an_answer_that_read_a_file_writes_nothing(tmp_path):
    folder = tmp_path / "capture"
    h = Harness(tmp_path, [say("From before: you are a data engineer.")])
    h.runner._capture = Capture(folder)
    earlier = Exchange(id=1, request="what does my cv say", reply="You are a data engineer.", did="read_text", tainted=True, run_id="r0")
    from stepout.domain import Task

    await h.runner.submit(Task(user_id="u", request="and what else?"), [earlier])
    assert not folder.exists() or list(folder.iterdir()) == []


def test_a_deleted_chats_files_go(tmp_path):
    capture = Capture(tmp_path)
    request = ModelRequest(model="m", system="s", user_text="u")
    response = ModelResponse(action=AnswerAction(text="a"), cost_usd=0.0)
    capture.write("run-1", "orchestrator", request, response)
    capture.write("run-2", "orchestrator", request, response)
    capture.remove(["run-1", "run-never-captured"])
    assert [p.name for p in tmp_path.iterdir()] == ["run-2.jsonl"]


def test_a_capture_that_cannot_be_written_does_not_raise(tmp_path):
    (tmp_path / "blocked").write_text("a file where the folder should be")
    request = ModelRequest(model="m", system="s", user_text="u")
    Capture(tmp_path / "blocked").write("run-1", "orchestrator", request, ModelResponse(action=AnswerAction(text="a"), cost_usd=0.0))
