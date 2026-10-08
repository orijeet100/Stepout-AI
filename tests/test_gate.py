from stepout import gate
from stepout.domain import AnswerAction, FetchAction, Allow, PlanAction, PlanStep, Refuse


def test_check_allows_known_actions():
    for action in [FetchAction(url="https://example.com"), AnswerAction(text="hi")]:
        assert isinstance(gate.check(action), Allow)


def test_each_role_holds_one_kind_of_hand():
    from stepout.roles import ROLES

    assert ROLES["orchestrator"].actions == {"plan", "delegate", "answer"}
    assert ROLES["direct"].actions == {"fetch", "answer"}
    assert ROLES["files"].actions == {"files", "answer"}
    assert ROLES["browser"].actions == {"browse", "answer"}
    assert ROLES["reader"].actions == {"read_text", "answer"}  # the only role that can open a file, and it holds nothing else


def test_a_role_can_only_take_its_own_actions():
    plan = PlanAction(steps=[PlanStep(role="direct", goal="x")])
    assert isinstance(gate.check(plan, frozenset({"plan", "answer"})), Allow)
    assert isinstance(gate.check(plan, frozenset({"fetch", "answer"})), Refuse)
    assert isinstance(gate.check(FetchAction(url="https://example.com"), frozenset({"plan"})), Refuse)
