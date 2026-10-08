"""Every Run leaves a row: what was asked, how it ended, what it cost."""

import asyncio

import pytest

from stepout.store import Store
from tests.support.scripted_model import ScriptedModel
from tests.test_runner import Harness, plan, say


def runs(tmp_path):
    """Read the file the Harness wrote, as a restarted server would."""
    return Store(tmp_path / "t.db").query("SELECT * FROM runs")


async def test_a_finished_run_and_its_task_are_saved(tmp_path):
    h = Harness(tmp_path, [say("5", cost=0.002)])
    task = await h.run("what is 2+3")

    (run,) = runs(tmp_path)
    assert (run["task_id"], run["outcome"], run["cap_usd"]) == (task.id, "done", 1.0)
    assert run["cost_usd"] == pytest.approx(0.002) and run["started_at"] <= run["ended_at"]
    (row,) = Store(tmp_path / "t.db").query("SELECT * FROM tasks")
    assert (row["id"], row["request"], row["conversation_id"]) == (task.id, "what is 2+3", "default")


async def test_pressing_stop_ends_the_run_as_cancelled(tmp_path):
    cancel = asyncio.Event()

    class StopsAfterFirstCall(ScriptedModel):
        async def call(self, request):
            response = await super().call(request)
            cancel.set()
            return response

    h = Harness(tmp_path, [], cancel=cancel)
    h.runner._model = StopsAfterFirstCall([plan("a"), say("never reached")])
    await h.run()
    assert [r["outcome"] for r in runs(tmp_path)] == ["cancelled"]


async def test_a_spent_budget_ends_the_run_as_cancelled(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")
    await Harness(tmp_path, [say("never reached")]).run()
    (run,) = runs(tmp_path)
    assert (run["outcome"], run["cap_usd"], run["cost_usd"]) == ("cancelled", 0.0, 0.0)


async def test_an_empty_answer_fails_the_run(tmp_path):
    await Harness(tmp_path, [say("  ")]).run()
    assert [r["outcome"] for r in runs(tmp_path)] == ["failed"]


async def test_a_crash_still_closes_the_run_row_as_failed(tmp_path):
    with pytest.raises(IndexError):  # the scripted model has nothing left to say
        await Harness(tmp_path, []).run()
    (run,) = runs(tmp_path)
    assert run["outcome"] == "failed" and run["ended_at"] is not None
