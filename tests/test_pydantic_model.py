"""PydanticModel: the same contract as AnthropicModel (tests/test_model.py), on Pydantic AI's model layer. Offline: a FunctionModel stands in for the provider."""

import pytest
from pydantic_ai import WebSearchTool
from pydantic_ai import messages as pai
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from stepout.domain import AnswerAction, BrowseAction, DelegateAction, FetchAction, FilesAction, PlanAction
from stepout.failure import Failure
from stepout.model import HAIKU, SONNET, ModelRequest
from stepout.pydantic_model import PydanticModel, from_env


def tool(name, **args):
    return pai.ToolCallPart(name, args)


def text(t):
    return pai.TextPart(t)


def searched():
    return pai.NativeToolCallPart(tool_name="web_search", args={"query": "q"})


def reply(*parts, model="claude-haiku-4-5", provider="anthropic", input_tokens=10, output_tokens=2):
    return pai.ModelResponse(parts=list(parts), usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens), model_name=model, provider_name=provider)


async def ask(*parts, **request):
    """Run one request through a PydanticModel whose provider returns `parts`; also return what the provider was sent."""
    seen: list[AgentInfo] = []

    def provider(messages, info: AgentInfo):
        seen.append(info)
        return reply(*(parts or [text("ok")]))

    model = PydanticModel({HAIKU: FunctionModel(provider, model_name="claude-haiku-4-5")})
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", **request))
    return response, seen[0]


async def test_a_request_without_tools_offers_none():
    _, info = await ask()
    assert info.function_tools == [] and info.model_request_parameters.native_tools == []


async def test_the_providers_search_runs_only_when_asked_for_and_is_capped():
    _, info = await ask(search=True, max_searches=1)
    assert info.function_tools == [] and info.model_request_parameters.native_tools == [WebSearchTool(max_uses=1)]


async def test_web_search_is_an_ordinary_function_tool_for_a_role():
    _, info = await ask(tools=["web_search", "fetch"])
    assert [t.name for t in info.function_tools] == ["web_search", "fetch"] and info.model_request_parameters.native_tools == []
    assert info.function_tools[0].metadata == {"reaches_web": True}


async def test_a_search_on_a_provider_that_cannot_search_fails_instead_of_answering_from_memory():
    class NoSearch(FunctionModel):
        supported_native_tools = classmethod(lambda cls: frozenset())

    model = PydanticModel({HAIKU: NoSearch(lambda messages, info: reply(text("made up")), model_name="claude-haiku-4-5")})
    with pytest.raises(Failure) as caught:
        await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", search=True))
    assert caught.value.kind == "no_search"


async def test_tool_calls_become_actions():
    steps = [{"role": "web_research", "goal": "find the news"}]
    cases = [
        (tool("fetch", url="https://example.com"), FetchAction(url="https://example.com")),
        (tool("plan", steps=steps), PlanAction(steps=steps)),
        (tool("delegate", step=0), DelegateAction(step=0)),
        (tool("files", op="find", path="D:\\", pattern="pdf"), FilesAction(op="find", path="D:\\", pattern="pdf")),
        (tool("files", op="count", path="D:\\"), FilesAction(op="count", path="D:\\")),
        (tool("browse", op="open", url="https://example.com"), BrowseAction(op="open", url="https://example.com")),
        (tool("browse", op="click", link=2), BrowseAction(op="click", link=2)),
        (tool("answer", text="done"), AnswerAction(text="done")),
    ]
    for part, expected in cases:
        response, _ = await ask(part, tools=["fetch"])
        assert response.action == expected


async def test_arguments_that_arrive_as_a_json_string_are_read():
    response, _ = await ask(pai.ToolCallPart("fetch", '{"url": "https://example.com"}'), tools=["fetch"])
    assert response.action == FetchAction(url="https://example.com")


async def test_a_text_only_reply_is_the_answer():
    response, _ = await ask(text("just words"), tools=["plan", "delegate", "answer"])
    assert response.action == AnswerAction(text="just words")


async def test_a_call_to_a_tool_that_was_not_offered_is_read_as_words():
    response, _ = await ask(text("hm"), tool("rm_rf", path="/"), tools=["fetch"])
    assert response.action == AnswerAction(text="hm")


async def test_only_the_first_tool_call_is_used_and_the_provider_is_asked_for_one():
    response, info = await ask(tool("fetch", url="https://a.example"), tool("fetch", url="https://b.example"), tools=["fetch"])
    assert response.action == FetchAction(url="https://a.example")
    assert info.model_settings["parallel_tool_calls"] is False


async def test_temperature_is_sent_only_when_asked():
    _, info = await ask()
    assert "temperature" not in info.model_settings
    _, info = await ask(temperature=0.0)
    assert info.model_settings["temperature"] == 0.0


async def test_searches_are_counted_and_priced():
    response, _ = await ask(searched(), searched(), text("x"))
    assert response.searches == 2
    assert response.cost_usd > 0.02


async def test_the_files_tool_needs_only_an_operation_and_a_path():
    _, info = await ask(tools=["files"])
    schema = info.function_tools[0].parameters_json_schema
    assert schema["required"] == ["op", "path"] and set(schema["properties"]) == {"op", "path", "pattern"}
    assert schema["properties"]["op"]["enum"] == ["list", "count", "find"]


async def test_the_browse_tool_and_the_browser_role_in_a_plan():
    _, info = await ask(tools=["browse", "plan"])
    by_name = {t.name: t.parameters_json_schema for t in info.function_tools}
    assert by_name["browse"]["required"] == ["op"] and by_name["browse"]["properties"]["op"]["enum"] == ["open", "click", "more"]
    assert "web_browsing" in by_name["plan"]["properties"]["steps"]["items"]["properties"]["role"]["enum"]


async def test_a_tool_that_reaches_the_web_says_so_for_the_gate():
    _, info = await ask(tools=["fetch", "files", "plan"])
    assert {t.name: t.metadata["reaches_web"] for t in info.function_tools} == {"fetch": True, "files": False, "plan": False}


async def test_a_one_off_tool_comes_back_as_a_tool_call():
    screen = {"name": "screen", "description": "d", "input_schema": {"type": "object", "properties": {"decision": {"type": "string"}}, "required": ["decision"]}}
    response, info = await ask(tool("screen", decision="proceed"), tool_defs=[screen])
    assert [t.name for t in info.function_tools] == ["screen"]
    assert response.action.kind == "tool_call" and response.action.input == {"decision": "proceed"}


async def test_a_call_with_missing_arguments_is_a_malformed_reply():
    with pytest.raises(Failure) as caught:
        await ask(tool("plan"), tools=["plan"])
    assert caught.value.kind == "malformed"


# --- price: the default route uses the table the Anthropic adapter uses; another route uses Pydantic AI's price table; an unknown price fails closed ---


def priced(model, provider, input_tokens, output_tokens):
    return reply(model=model, provider=provider, input_tokens=input_tokens, output_tokens=output_tokens)


def test_the_default_route_prices_from_the_same_table_as_the_anthropic_adapter():
    cost = PydanticModel()._cost(HAIKU, priced("claude-haiku-4-5", "anthropic", 1_000_000, 1_000_000), searches=1)
    assert cost == pytest.approx(1.00 + 5.00 + 0.01)


def test_another_route_is_priced_by_the_published_price_of_the_model_that_answered():
    model = PydanticModel({SONNET: "openrouter:openai/gpt-5.2"})
    cost = model._cost(SONNET, priced("openai/gpt-5.2", "openrouter", 10_000, 1_000), searches=0)
    assert 0.01 < cost < 0.1


def test_a_model_with_no_known_price_fails_closed_instead_of_reading_as_free():
    model = PydanticModel({SONNET: "openrouter:acme/made-up-model"})
    with pytest.raises(Failure) as caught:
        model._cost(SONNET, priced("acme/made-up-model", "openrouter", 10, 10), searches=0)
    assert caught.value.kind == "pricing" and "made-up-model" in caught.value.message


# --- failures: one line for the User, the cause for the Ledger ---


async def failing(exc):
    def provider(messages, info):
        raise exc

    model = PydanticModel({HAIKU: FunctionModel(provider, model_name="claude-haiku-4-5")})
    with pytest.raises(Failure) as caught:
        await model.call(ModelRequest(model=HAIKU, system="s", user_text="u"))
    return caught.value


@pytest.mark.parametrize(
    "exc, kind",
    [
        (ModelHTTPError(401, "m"), "auth"),
        (ModelHTTPError(403, "m"), "auth"),
        (ModelHTTPError(402, "m"), "credit"),
        (ModelHTTPError(400, "m", {"error": {"message": "Your credit balance is too low"}}), "credit"),
        (ModelHTTPError(429, "m"), "rate_limit"),
        (ModelHTTPError(503, "m"), "server_error"),
        (ModelHTTPError(400, "m", {"error": "bad"}), "rejected"),
        (ModelAPIError("m", "connection reset"), "connection"),
    ],
)
async def test_a_provider_failure_becomes_a_plain_line(exc, kind):
    failure = await failing(exc)
    assert failure.kind == kind and failure.message and "Traceback" not in failure.message


async def test_a_provider_with_no_key_says_which_key_and_where(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    model = PydanticModel({HAIKU: "openrouter:openai/gpt-5.2"})
    with pytest.raises(Failure) as caught:
        await model.call(ModelRequest(model=HAIKU, system="s", user_text="u"))
    assert caught.value.kind == "no_key" and ".env" in caught.value.message


# --- config ---


def test_nothing_set_means_no_override():
    assert from_env({}) is None and from_env({"STEPOUT_STRONG_MODEL": "  "}) is None


def test_the_two_tiers_are_set_from_the_environment():
    model = from_env({"STEPOUT_STRONG_MODEL": "openrouter:openai/gpt-5.2", "STEPOUT_CHEAP_MODEL": "openrouter:google/gemini-3-flash-preview"})
    assert model.target(SONNET) == "openrouter:openai/gpt-5.2" and model.target(HAIKU) == "openrouter:google/gemini-3-flash-preview"


def test_a_tier_left_unset_runs_as_itself_on_anthropic():
    model = from_env({"STEPOUT_CHEAP_MODEL": "openrouter:google/gemini-3-flash-preview"})
    assert model.target(SONNET) == f"anthropic:{SONNET}"


def test_the_start_up_check_asks_only_for_the_keys_the_tiers_need():
    assert PydanticModel().key_vars() == ["ANTHROPIC_API_KEY"]
    both = PydanticModel({SONNET: "openrouter:a/b", HAIKU: "openrouter:c/d"})
    assert both.key_vars() == ["OPENROUTER_API_KEY"]
    mixed = PydanticModel({HAIKU: "openrouter:c/d"})
    assert mixed.key_vars() == ["ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]


def test_the_app_runs_the_anthropic_adapter_unless_a_tier_is_re_pointed():
    from stepout.model import AnthropicModel
    from stepout.pydantic_model import default_model

    assert isinstance(default_model({}), AnthropicModel)
    assert isinstance(default_model({"STEPOUT_CHEAP_MODEL": "openrouter:a/b"}), PydanticModel)


def test_the_start_up_note_names_the_key_the_chosen_models_need(monkeypatch, tmp_path):
    from stepout import app

    (tmp_path / "grants.toml").write_text("")
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    notes = app.startup_notes(["OPENROUTER_API_KEY"])
    assert len(notes) == 1 and "OPENROUTER_API_KEY" in notes[0] and "ANTHROPIC" not in notes[0]
