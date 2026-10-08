"""The page and the backend promise each other the shapes of docs/ui-contract.md; these tests keep both sides honest."""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from stepout import history
from stepout.contract import ClientFrame, ServerFrame
from tests.test_history import ask, serve
from tests.test_runner import FakeBrowser, browse, plan, say

FIXTURES = sorted((Path(__file__).resolve().parents[1] / "web" / "fixtures").glob("*.json"))
AT = "2026-10-07T12:00:00+00:00"


def test_every_ui_fixture_is_a_list_of_valid_server_frames():
    if not FIXTURES:
        pytest.skip("no web/fixtures yet: the UI lane's U2 adds them")
    for path in FIXTURES:
        try:
            TypeAdapter(list[ServerFrame]).validate_python(json.loads(path.read_text(encoding="utf-8")))
        except ValidationError as exc:  # a fixture the backend would never send, or a field the contract lacks
            pytest.fail(f"{path.name} does not match src/stepout/contract.py (a fixture is a JSON list of server frames):\n{exc}")


def test_the_fixture_check_passes_a_good_fixture_and_names_a_bad_one(tmp_path, monkeypatch):
    # The real check skips until the UI lane adds web/fixtures; this shows it would catch drift once they exist.
    good = tmp_path / "good.json"
    good.write_text(json.dumps([{"type": "hello", "v": 1}, {"type": "message", "id": "m", "conversation_id": "c", "role": "user", "text": "hi", "at": AT}]))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"type": "message", "id": "m", "conversation_id": "c", "role": "user", "text": "hi", "at": AT, "colour": "red"}]))
    monkeypatch.setitem(globals(), "FIXTURES", [good])
    test_every_ui_fixture_is_a_list_of_valid_server_frames()
    monkeypatch.setitem(globals(), "FIXTURES", [good, bad])
    with pytest.raises(pytest.fail.Exception, match="bad.json"):
        test_every_ui_fixture_is_a_list_of_valid_server_frames()


def test_the_contracts_own_examples_are_valid_and_a_stray_field_is_drift():
    server = [
        {"type": "hello", "v": 1},
        {"type": "message", "id": "m1", "conversation_id": "c1", "role": "assistant", "text": "hi", "run_id": "r1", "cost_usd": 0.01, "at": AT},
        {"type": "message", "id": "m0", "conversation_id": "c1", "role": "user", "text": "hello", "at": AT},
        {"type": "trace", "id": "e1", "conversation_id": "c1", "run_id": "r1", "parent": None, "kind": "step", "role": "orchestrator", "data": {"summary": "answer"}, "cost_usd": 0.0064, "at": AT},
        {"type": "status", "state": "running", "active": {"conversation_id": "c1", "run_id": "r1", "cap_usd": 1.0}, "queued": [{"conversation_id": "c2"}], "at": AT},
        {"type": "status", "state": "idle", "active": None, "queued": [], "at": AT},
    ]
    TypeAdapter(list[ServerFrame]).validate_python(server)
    TypeAdapter(list[ClientFrame]).validate_python([{"type": "send", "conversation_id": "c1", "text": "hi"}, {"type": "stop"}])
    with pytest.raises(ValidationError):
        TypeAdapter(ServerFrame).validate_python({**server[1], "surprise": 1})


# What the contract's table promises each kind of trace event carries in `data`.
def check_plan(d):
    assert d["steps"] and all(s["role"] and s["goal"] and s["status"] in ("pending", "running", "done", "failed") for s in d["steps"])


def check_step(d):
    assert d["action"]["kind"] and d["verdict"] in ("allow", "refuse", "ask")


def check_return(d):
    assert isinstance(d["ok"], bool)


def check_shot(d):
    assert d["shot"] and d["url"] and "title" in d


DATA_CHECKS = {"plan": check_plan, "step": check_step, "return": check_return, "shot": check_shot, "stop": lambda d: None}


async def test_what_the_runner_emits_matches_the_contracts_event_table(tmp_path, monkeypatch):
    page = ("URL: https://example.com\nTitle: Example\nText: Example Domain", "abc/1.jpg")
    script = [plan("read it", role="browser"), plan("sneaky", role="browser"), browse("open", "https://example.com"), say("found"), say("done")]  # the 2nd plan is refused
    reopened = await serve(tmp_path, [ask("c1", "read https://example.com")], script, browser=FakeBrowser(page))
    monkeypatch.setenv("STEPOUT_TASK_CAP_USD", "0")  # set after the first Run started, so only this one has no budget and stops
    stopped = await serve(tmp_path / "2", [ask("c1", "what is the capital of France?")], [])

    events = []
    for store in (reopened, stopped):
        (run,) = history.get_conversation(store, "c1").runs
        events += history.run_events(store, run.run_id)
    assert {e.kind for e in events} == set(DATA_CHECKS)  # every kind the table lists occurred
    assert any(e.kind == "step" and e.data["verdict"] == "refuse" for e in events)
    for e in events:
        assert e.data["summary"], e
        DATA_CHECKS[e.kind](e.data)
    assert [e.cost_usd for e in events if e.kind == "step"][0] > 0  # a step's cost is that model call's
