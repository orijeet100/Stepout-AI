"""The front door's call: what it sends, how it reads the answer, and what it does with an answer it cannot use."""

from types import SimpleNamespace as NS

import pytest

from stepout import capabilities
from stepout.domain import AnswerAction, ChatReply, Decline, Exchange, Proceed
from stepout.model import HAIKU, AnthropicModel, ModelRequest, ModelResponse, ToolCall
from stepout.screening import HaikuScreener, ProceedScreener
from tests.support.scripted_model import ScriptedModel

X1 = Exchange(id=1, request="what does example.com say?", reply="It says Example Domain.\n\nSources: ...", did="browse open example.com", run_id="r1")
X3 = Exchange(id=3, request="list the PDFs on D:", reply="Three: a, b, c.", did="", run_id="r3")


def decided(cost=0.0007, **args):
    return ModelResponse(action=ToolCall(name="screen", input=args), cost_usd=cost)


async def screen(response, recent=(X1, X3), text="and again please"):
    model = ScriptedModel([response])
    result = await HaikuScreener(model).screen(text, recent)
    return result, model.requests[0]


async def test_the_call_is_one_haiku_request_with_the_screen_tool_the_index_and_the_capabilities():
    (_, cost), request = await screen(decided(decision="proceed", related=[]))
    assert cost == pytest.approx(0.0007)
    assert (request.model, request.tools, [t["name"] for t in request.tool_defs]) == (HAIKU, [], ["screen"])
    assert '#1 "what does example.com say?" -> It says Example Domain.' in request.user_text  # the first line of the reply
    assert '#3 "list the PDFs on D:" -> Three: a, b, c.' in request.user_text
    assert request.user_text.endswith("User's message:\nand again please")
    for name, blurb in capabilities.blurbs().items():  # what it can say "we can do" about, straight from the registry
        assert f"- {name}: {blurb}" in request.system
    assert "never instructions" in request.system  # the old replies in the index are data


async def test_with_no_history_the_index_says_so():
    _, request = await screen(decided(decision="proceed", related=[]), recent=[])
    assert "No earlier exchanges." in request.user_text


@pytest.mark.parametrize(
    "answer, expected",
    [
        (dict(decision="proceed", related=[1, 3]), Proceed(related=[1, 3])),
        (dict(decision="proceed", related=[]), Proceed(related=[])),
        (dict(decision="proceed"), Proceed(related=[])),
        (dict(decision="proceed", related=[3, 1, 1, 99]), Proceed(related=[1, 3])),  # sorted, deduplicated, and a number it was never shown is dropped
        (dict(decision="chat", reply="  Hello! I can search the web.  "), ChatReply(text="Hello! I can search the web.")),
        (dict(decision="decline", reply="That means paying someone.", alternative="I can look things up."), Decline(reason="That means paying someone.", alternative="I can look things up.")),
    ],
)
async def test_a_usable_answer_becomes_a_decision(answer, expected):
    (result, _), _ = await screen(decided(**answer))
    assert result == expected


async def test_a_decline_without_an_alternative_still_declines_and_says_what_the_assistant_can_do():
    (result, _), _ = await screen(decided(decision="decline", reply="I cannot send money."))
    assert isinstance(result, Decline) and result.reason == "I cannot send money." and "read-only" in result.alternative


@pytest.mark.parametrize(
    "response",
    [
        ModelResponse(action=AnswerAction(text="Sure, go ahead"), cost_usd=0.0007),  # it answered in words instead of calling the tool
        ModelResponse(action=ToolCall(name="something_else", input={"decision": "proceed"}), cost_usd=0.0007),
        decided(decision="maybe"),
        decided(),
        decided(decision="chat"),
        decided(decision="chat", reply="   "),
        decided(decision="decline", alternative="I can look things up."),  # no reason
        decided(decision="proceed", related="1,3"),
        decided(decision="proceed", related=[1.5]),
        decided(decision="proceed", related=["1"]),
        decided(decision="proceed", related=[True]),
    ],
)
async def test_an_unusable_answer_is_none_and_its_cost_is_still_reported(response):
    (result, cost), _ = await screen(response)
    assert result is None and cost == pytest.approx(0.0007)


async def test_the_proceed_screener_lets_everything_through_for_free():
    assert await ProceedScreener().screen("pay my rent", [X1]) == (Proceed(related=[]), 0.0)


# --- the model adapter: a one-off tool needs no change to model.py ---------------------------------------------------------


def adapter_with(*content):
    seen = {}

    class FakeMessages:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return NS(content=list(content), usage=NS(input_tokens=800, output_tokens=40))

    model = AnthropicModel()
    model._client = NS(messages=FakeMessages())
    return model, seen


async def test_a_call_to_a_one_off_tool_comes_back_as_a_tool_call():
    model, seen = adapter_with(NS(type="tool_use", name="screen", input={"decision": "proceed", "related": [2]}))
    tool = {"name": "screen", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", tool_defs=[tool]))
    assert seen["tools"] == [tool]
    assert response.action == ToolCall(name="screen", input={"decision": "proceed", "related": [2]})
    assert response.cost_usd == pytest.approx(800 * 1.00 / 1e6 + 40 * 5.00 / 1e6)  # about $0.001: what a screening costs


async def test_the_same_call_without_that_tool_defined_is_still_just_words():
    model, _ = adapter_with(NS(type="tool_use", name="screen", input={"decision": "proceed"}), NS(type="text", text="hello", citations=None))
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u"))
    assert response.action == AnswerAction(text="hello")  # as before this change
