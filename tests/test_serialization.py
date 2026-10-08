from pydantic import TypeAdapter

from stepout.domain import (
    Action,
    AnswerAction,
    DelegateAction,
    FetchAction,
    PlanAction,
    PlanStep,
)

ACTIONS = [
    FetchAction(url="https://example.com"),
    AnswerAction(text="hi"),
    PlanAction(steps=[PlanStep(role="direct", goal="find the news", status="running")]),
    DelegateAction(step=0),
]


def test_actions_round_trip_through_json():
    adapter = TypeAdapter(Action)
    for action in ACTIONS:
        restored = adapter.validate_json(adapter.dump_json(action))
        assert restored == action
