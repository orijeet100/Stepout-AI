"""Capabilities: a new one is one file plus one registration line, and the core never has to learn its name."""

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from pydantic import TypeAdapter, ValidationError

from stepout import capabilities, gate
from stepout.domain import Action, AnswerAction, Allow, BrowseAction, FetchAction, FilesAction, PlanStep, Refuse, Task
from stepout.ledger import Ledger
from stepout.model import HAIKU, AnthropicModel, ModelRequest, ModelResponse, _tool_defs
from stepout.roles import ROLES, SPECIALISTS
from stepout.runner import Runner
from stepout.store import Store
from tests.support import echo_capability
from tests.support.echo_capability import Echo, EchoAction
from tests.support.scripted_model import ScriptedModel

CORE = {f"stepout.{m}" for m in ("domain", "model", "gate", "runner", "roles")}


def test_the_fake_capability_imports_none_of_the_core():
    imported = set()
    for node in ast.walk(ast.parse(Path(echo_capability.__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {node.module, *(f"{node.module}.{a.name}" for a in node.names)}
    assert not imported & CORE, imported & CORE


@pytest.fixture
def with_echo(monkeypatch):
    """The one registration line, plus giving the Orchestrator the tool (a Role's tools are names)."""
    monkeypatch.setattr(capabilities, "ALL", [*capabilities.ALL, Echo()])
    orchestrator = ROLES["orchestrator"]
    monkeypatch.setitem(ROLES, "orchestrator", replace(orchestrator, tools=(*orchestrator.tools, "echo")))


def echo(text):
    return ModelResponse(action=EchoAction(text=text), cost_usd=0.001)


async def run_task(tmp_path, responses):
    ledger, replies, traced = Ledger(Store(tmp_path / "t.db")), [], []

    async def notify(reply):
        replies.append(reply)

    async def trace(event):
        traced.append(event)

    model = ScriptedModel(responses)
    await Runner(model, object(), ledger, notify, trace).submit(Task(user_id="u", request="say hi"))
    return model, replies, traced


async def test_a_registered_capability_runs_through_the_runner(with_echo, tmp_path):
    model, replies, traced = await run_task(tmp_path, [echo("hi"), echo("hi"), ModelResponse(action=AnswerAction(text="done"), cost_usd=0.001)])

    assert "echo" in model.requests[0].tools  # offered to the Role that holds it
    assert "echo: hi" in model.requests[1].user_text  # its result reached the Role's notes
    assert "already ran exactly this" in model.requests[2].user_text  # the repeat guard held
    steps = [e for e in traced if e.kind == "step"]
    assert [e.data["summary"] for e in steps] == ["echo hi", "echo hi", "answer"]  # its Trace line
    assert all(e.data["verdict"] == "allow" for e in steps)
    note = next(e for e in traced if e.kind == "note")  # ctx.emit hangs its event under the Step that ran
    assert note.parent == steps[0].id and note.role == "orchestrator"
    assert replies[0].text.startswith("done")


async def test_a_capability_can_refuse_through_its_own_gate_rule(monkeypatch, tmp_path):
    class NoEchoes(Echo):
        def check(self, action, ctx):
            return Refuse(reason="no echoes today")

    monkeypatch.setattr(capabilities, "ALL", [*capabilities.ALL, NoEchoes()])
    orchestrator = ROLES["orchestrator"]
    monkeypatch.setitem(ROLES, "orchestrator", replace(orchestrator, tools=(*orchestrator.tools, "echo")))
    model, _, traced = await run_task(tmp_path, [echo("hi"), ModelResponse(action=AnswerAction(text="ok"), cost_usd=0.001)])

    assert "Refused: no echoes today" in model.requests[1].user_text
    assert [e.data["verdict"] for e in traced if e.kind == "step"] == ["refuse", "allow"]
    assert not any(e.kind == "note" for e in traced)  # it never ran


def test_a_role_that_does_not_hold_the_capability_is_refused(with_echo):
    assert isinstance(gate.check(EchoAction(text="x"), ROLES["direct"].actions), Refuse)
    assert isinstance(gate.check(EchoAction(text="x"), frozenset({"echo", "answer"})), Allow)


async def test_the_model_adapter_needs_no_edit_for_a_new_capability(with_echo):
    seen = {}

    class FakeMessages:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return NS(content=[NS(type="tool_use", name="echo", input={"text": "yo"})], usage=NS(input_tokens=1, output_tokens=1))

    model = AnthropicModel()
    model._client = NS(messages=FakeMessages())
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", tools=["echo"]))
    assert seen["tools"][0]["name"] == "echo" and seen["tools"][0]["input_schema"]["required"] == ["text"]
    assert response.action == EchoAction(text="yo")


def test_blurbs_cover_every_capability():
    blurbs = capabilities.blurbs()
    assert set(blurbs) == {c.name for c in capabilities.ALL}
    assert all(b.strip() for b in blurbs.values())


def test_every_role_tool_is_a_capability_or_a_control_tool():
    known = {c.name for c in capabilities.ALL} | {"plan", "delegate", "answer"}
    assert {t for role in ROLES.values() for t in role.tools} <= known


def test_a_tool_the_provider_runs_has_no_action_and_is_not_one_a_role_may_take():
    search = capabilities.get("web_search")
    assert search.action is None and capabilities.parse("web_search", {}) is None
    assert ROLES["direct"].actions == {"fetch", "answer"}


def test_plan_roles_come_from_the_role_table():
    assert SPECIALISTS == ("direct", "files", "browser")
    for name in SPECIALISTS:
        assert PlanStep(role=name, goal="g").role == name
        assert f"{name} (" in ROLES["orchestrator"].system  # the prompt describes every role a Plan can name
    with pytest.raises(ValidationError):
        PlanStep(role="orchestrator", goal="g")
    plan = next(t for t in _tool_defs(ModelRequest(model=HAIKU, system="s", user_text="u", tools=["plan"])))
    assert plan["input_schema"]["properties"]["steps"]["items"]["properties"]["role"]["enum"] == list(SPECIALISTS)


def test_the_action_union_round_trips_every_capability_action():
    adapter = TypeAdapter(Action)
    samples = [FetchAction(url="https://example.com"), FilesAction(op="find", path="D:\\Docs", pattern="cv"), BrowseAction(op="open", url="https://example.com")]
    assert {type(s) for s in samples} <= set(capabilities.action_types())
    for action in samples:
        assert adapter.validate_json(adapter.dump_json(action)) == action
