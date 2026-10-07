from pydantic import TypeAdapter

from stepout.domain import Action, AnswerAction, FetchAction, Result, FetchResult, SearchAction, SearchResult, AnswerResult

ACTIONS = [
    FetchAction(url="https://example.com"),
    SearchAction(query="weather", snippets=["a", "b"]),
    AnswerAction(text="hi"),
]
RESULTS = [
    FetchResult(url="https://example.com", text="hello"),
    SearchResult(query="weather", snippets=["a"]),
    AnswerResult(text="hi"),
]


def test_actions_round_trip_through_json():
    adapter = TypeAdapter(Action)
    for action in ACTIONS:
        restored = adapter.validate_json(adapter.dump_json(action))
        assert restored == action


def test_results_round_trip_through_json():
    adapter = TypeAdapter(Result)
    for result in RESULTS:
        restored = adapter.validate_json(adapter.dump_json(result))
        assert restored == result
