import json
import logging

import pytest
from pydantic import BaseModel, ValidationError

from stepout import logs, scope
from stepout.failure import Failure
from stepout.scope import RunScope


@pytest.fixture
def log(tmp_path):
    path = logs.configure(tmp_path / "logs", environ={})
    yield path
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "_stepout_log", False)]:
        root.removeHandler(handler)
        handler.close()


def lines(path):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_line_inside_a_run_carries_the_run_and_chat(log):
    token = scope.enter(RunScope(run_id="r1", task_id="t1", conversation_id="c1"))
    try:
        logging.getLogger("stepout.test").info("inside")
    finally:
        scope.leave(token)
    logging.getLogger("stepout.test").info("outside")

    inside, outside = lines(log)
    assert (inside["run_id"], inside["conversation_id"], inside["msg"]) == ("r1", "c1", "inside")
    assert "run_id" not in outside and outside["msg"] == "outside"


def test_an_exception_that_echoes_its_input_is_logged_without_its_message(log):
    class Row(BaseModel):
        n: int

    try:
        Row(n="hunter2-the-password-in-the-file")
    except ValidationError:
        logging.getLogger("stepout.test").exception("a reply could not be read")

    (line,) = lines(log)
    assert line["exc_type"] == "ValidationError" and line["frames"]
    assert "exc_message" not in line and "hunter2" not in json.dumps(line)


def test_a_failures_own_plain_message_is_kept(log):
    try:
        raise Failure("rate_limit", "The provider is rate-limiting requests right now.")
    except Failure:
        logging.getLogger("stepout.test").exception("run failed")

    (line,) = lines(log)
    assert line["exc_type"] == "Failure" and line["exc_message"].startswith("The provider is rate-limiting")


def test_the_level_comes_from_the_environment(tmp_path):
    try:
        path = logs.configure(tmp_path / "logs", environ={"STEPOUT_LOG_LEVEL": "warning"})
        logging.getLogger("stepout.test").info("quiet")
        logging.getLogger("stepout.test").warning("loud")
        assert [line["msg"] for line in lines(path)] == ["loud"]
    finally:
        for handler in [h for h in logging.getLogger().handlers if getattr(h, "_stepout_log", False)]:
            logging.getLogger().removeHandler(handler)
            handler.close()
        logging.getLogger().setLevel(logging.WARNING)


def test_configuring_twice_does_not_write_a_line_twice(tmp_path, log):
    logs.configure(tmp_path / "logs", environ={})
    logging.getLogger("stepout.test").info("once")
    assert [line["msg"] for line in lines(log)] == ["once"]


def test_the_file_rotates_and_keeps_a_bounded_number(tmp_path):
    try:
        path = logs.configure(tmp_path / "logs", environ={}, max_bytes=2_000)
        for i in range(400):
            logging.getLogger("stepout.test").info("line %d %s", i, "x" * 40)
        for handler in logging.getLogger().handlers:
            handler.flush()
        files = sorted(p.name for p in path.parent.iterdir())
        assert len(files) <= 6 and files[0] == "stepout.log"  # the live file and at most five older ones
    finally:
        for handler in [h for h in logging.getLogger().handlers if getattr(h, "_stepout_log", False)]:
            logging.getLogger().removeHandler(handler)
            handler.close()


async def test_a_run_that_fails_leaves_a_line_with_its_run_id(tmp_path, log):
    from tests.test_runner import Harness

    h = Harness(tmp_path, [])  # the model has nothing to say: an unexpected error inside the Run
    task = await h.run("do it")

    run_id = h.ledger.query(task.id)[-1].run_id
    failed = [line for line in lines(log) if line["level"] == "ERROR"]
    assert failed and failed[0]["run_id"] == run_id and failed[0]["exc_type"] == "IndexError"
