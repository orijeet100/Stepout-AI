"""The front door's call: what it sends, how it reads the answer, and what it does with an answer it cannot use."""

from types import SimpleNamespace as NS

import pytest

from stepout import capabilities
from stepout.domain import AnswerAction, ChatReply, Decline, Exchange, Proceed
from stepout.model import HAIKU, AnthropicModel, ModelRequest, ModelResponse, ToolCall
from stepout.screening import _SCREEN_TOOL, _SYSTEM, HaikuScreener
from tests.support.screening_eval import load_rows
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
        (dict(decision="chat", chat_kind="greeting", reply="  Hello! I can search the web.  ", related=[]), ChatReply(text="Hello! I can search the web.")),
        (dict(decision="chat", chat_kind="thanks", reply="You're welcome!"), ChatReply(text="You're welcome!")),  # related missing means none
        (dict(decision="proceed", related=None), Proceed(related=[])),  # null means none too: an answer the old parser threw away
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


# --- the model adapter: a one-off tool needs no change to model.py ---------------------------------------------------------


def adapter_with(*content):
    seen = {}

    class FakeMessages:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return NS(content=list(content), usage=NS(input_tokens=800, output_tokens=40))

    model = AnthropicModel()
    model._client = NS(messages=FakeMessages(), api_key="test")
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


# --- chat is allowed only for what the prompt allows --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer, text, expected",
    [
        (dict(decision="chat", reply="51"), "What is 17 times 3?", Proceed()),  # an ordinary question it tried to answer itself
        (dict(decision="chat", chat_kind="question", reply="Paris."), "capital of France?", Proceed()),  # not one of the three kinds
        (dict(decision="chat", chat_kind="about_assistant", reply="Those events are free.", related=[1]), "which of those events are free?", Proceed(related=[1])),
        (dict(decision="chat", chat_kind="about_assistant", reply="Sure.", related=[99]), "tell me more", Proceed()),  # it claimed a dependency it was never shown
        (dict(decision="chat", chat_kind="greeting", reply="Hi!"), "hello can you also tell me what the capital of France is", Proceed()),  # a greeting that asks for more
    ],
)
async def test_a_chat_that_is_not_plain_chat_goes_to_the_assistant_behind_it(answer, text, expected):
    (result, cost), _ = await screen(decided(**answer), text=text)
    assert result == expected and cost == pytest.approx(0.0007)  # a downgrade is a proceed, not a failure: no fallback, the cost is kept


async def test_plain_chat_is_still_chat():
    for text, kind in [("hi", "greeting"), ("thanks, that was helpful", "thanks"), ("what are you able to help with?", "about_assistant")]:
        (result, _), _ = await screen(decided(decision="chat", chat_kind=kind, reply="Hello!", related=[]), recent=[], text=text)
        assert result == ChatReply(text="Hello!"), text


async def test_a_chat_answer_with_a_malformed_link_list_is_unusable():
    (result, _), _ = await screen(decided(decision="chat", chat_kind="greeting", reply="hi", related="x"))
    assert result is None


def test_the_tool_makes_the_model_name_a_kind_and_always_give_related():
    schema = _SCREEN_TOOL["input_schema"]
    assert schema["required"] == ["decision", "related"]
    assert schema["properties"]["chat_kind"]["enum"] == ["greeting", "thanks", "about_assistant"]


def test_the_prompt_makes_proceed_the_default_and_none_of_the_eval_prompts_is_in_it():
    assert "the default" in _SYSTEM and "NEVER answer these yourself" in _SYSTEM and "never chat" in _SYSTEM
    for row in load_rows():  # an example in the prompt that is also an eval row would make the eval measure memory
        assert f'"{row["prompt"].lower()}"' not in _SYSTEM.lower(), row["prompt"]


async def test_the_screener_keeps_the_models_raw_answer_for_the_eval_to_show():
    screener = HaikuScreener(ScriptedModel([decided(decision="proceed", related=[1])]))
    await screener.screen("again", [X1])
    assert screener.last_answer == {"decision": "proceed", "related": [1]}
    words = HaikuScreener(ScriptedModel([ModelResponse(action=AnswerAction(text="Sure, go ahead"), cost_usd=0.0)]))
    await words.screen("again", [X1])
    assert words.last_answer == {"no tool call": "Sure, go ahead"}


# --- stability: temperature 0, and what the live runs showed ---------------------------------------------------------------


async def test_the_screening_call_asks_for_temperature_zero_and_is_the_only_one_that_does():
    _, request = await screen(decided(decision="proceed", related=[]))
    assert request.temperature == 0.0
    assert ModelRequest(model=HAIKU, system="s", user_text="u").temperature is None  # every other call keeps the API default


def test_tripwire_temperature_is_only_allowed_on_models_released_before_opus_4_6():
    # Official reference: "Models released after Claude Opus 4.6 do not support setting temperature. A value of 1.0 will be accepted ...,
    # all other values will be rejected with a 400 error." The screening call sets 0, so the day HAIKU moves to a newer model, every screening
    # would fail (and fall back, fail open, unnoticed). If this test fails, read that note and drop `temperature=0.0` or keep the old model.
    assert HAIKU == "claude-haiku-4-5"


async def test_temperature_reaches_the_wire_through_the_real_sdk_only_when_asked_for():
    # Through the real anthropic client over a mock HTTP transport (no network). A fake client accepts any keyword, which is how this once
    # passed offline while the real SDK (1.x: no `temperature` argument on create()) raised TypeError on every screening.
    import json

    import anthropic

    try:
        import httpx2 as httpx  # the HTTP library anthropic 1.x uses
    except ImportError:
        import httpx

    bodies = []

    def answer(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "msg_1", "type": "message", "role": "assistant", "model": HAIKU, "stop_reason": "end_turn", "stop_sequence": None,
                                         "content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 1, "output_tokens": 1}})

    model = AnthropicModel()
    model._client = anthropic.AsyncAnthropic(api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    await model.call(ModelRequest(model=HAIKU, system="s", user_text="u"))
    await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", temperature=0.0))
    assert "temperature" not in bodies[0] and bodies[1]["temperature"] == 0.0


def test_a_message_that_only_lacks_something_is_not_a_decline_and_scripts_count_as_software():
    # Live runs 2 and 3: "delete the duplicate lines from this list" and "summarize this article about ..." (nothing attached) were declined
    # ("I need you to provide the list first") or answered in words; "write me a python script" went on in both runs.
    assert "A request that only lacks something" in _SYSTEM and "is NOT a decline" in _SYSTEM
    assert "scripts, apps, websites" in _SYSTEM
