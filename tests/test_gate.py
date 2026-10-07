from stepout import gate
from stepout.domain import Accept, AnswerAction, Decline, FetchAction, Allow, PlanAction, PlanStep, Refuse, SearchAction, Unsure

FORBIDDEN_CASES = [
    "pay this invoice",
    "cancel my subscription",
    "delete my account",
    "change my password",
    "create an account for me on this site",
    "build me a website",
]

LOOKUP_CASES = ["what's the weather in Chicago?", "latest news on X"]
UNSURE_CASES = ["hi", "ok"]
ANSWER_CASES = ["what is the capital of France?"]


def test_forbidden_requests_are_declined():
    for text in FORBIDDEN_CASES:
        result = gate.screen(text)
        assert isinstance(result, Decline), text


def test_lookup_hints_route_to_lookup():
    for text in LOOKUP_CASES:
        result = gate.screen(text)
        assert isinstance(result, Accept)
        assert result.route == "lookup"


def test_short_ambiguous_text_is_unsure():
    for text in UNSURE_CASES:
        assert isinstance(gate.screen(text), Unsure), text


def test_longer_plain_questions_default_to_answer():
    for text in ANSWER_CASES:
        result = gate.screen(text)
        assert isinstance(result, Accept)
        assert result.route == "answer"


def test_check_allows_known_actions():
    for action in [FetchAction(url="https://example.com"), SearchAction(query="x", snippets=[]), AnswerAction(text="hi")]:
        assert isinstance(gate.check(action), Allow)


def test_each_role_holds_one_kind_of_hand():
    from stepout.roles import ROLES

    assert ROLES["orchestrator"].actions == {"plan", "delegate", "answer"}
    assert ROLES["direct"].actions == {"fetch", "answer"}
    assert ROLES["files"].actions == {"files", "answer"}


def test_a_role_can_only_take_its_own_actions():
    plan = PlanAction(steps=[PlanStep(role="direct", goal="x")])
    assert isinstance(gate.check(plan, frozenset({"plan", "answer"})), Allow)
    assert isinstance(gate.check(plan, frozenset({"fetch", "answer"})), Refuse)
    assert isinstance(gate.check(FetchAction(url="https://example.com"), frozenset({"plan"})), Refuse)
