"""The Searcher: one provider search per call, reported with its cost. (How a search is a step the Gate and the Trace see: tests/test_runner.py, tests/test_taint.py.)"""

from stepout.domain import AnswerAction
from stepout.model import HAIKU, ModelResponse
from stepout.search import Searcher
from tests.support.scripted_model import ScriptedModel


async def test_the_searcher_asks_for_one_provider_search_and_reports_what_it_found_and_what_it_cost():
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="  Found X [a](https://a.example)  "), cost_usd=0.01)])
    text, cost = await Searcher(model).search("what is x")
    (request,) = model.requests
    assert request.search and request.max_searches == 1 and request.tools == [] and request.user_text == "what is x" and request.model == HAIKU
    assert text == "Found X [a](https://a.example)" and cost == 0.01


async def test_an_empty_answer_says_nothing_was_found():
    model = ScriptedModel([ModelResponse(action=AnswerAction(text="  "), cost_usd=0.002)])
    text, cost = await Searcher(model).search("q")
    assert text == "The search found nothing." and cost == 0.002


async def test_a_fourth_search_in_one_run_is_not_run():
    from stepout.capabilities.base import RunContext
    from stepout.capabilities.web_search import MAX_SEARCHES, WebSearch, WebSearchAction

    class Counting:
        calls = 0

        async def search(self, query):
            Counting.calls += 1
            return f"found {query}", 0.0

    ctx = RunContext(run_id="r", role="direct", hands={"web_search": Counting()}, cancelled=lambda: False, emit=None)
    results = [await WebSearch().run(WebSearchAction(query=str(i)), ctx) for i in range(MAX_SEARCHES + 1)]
    assert Counting.calls == MAX_SEARCHES and "No searches left" in results[-1]  # the fourth made no call of its own
