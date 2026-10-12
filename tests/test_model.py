from types import SimpleNamespace as NS

from stepout.domain import AnswerAction, BrowseAction, DelegateAction, FetchAction, FilesAction, PlanAction
from stepout.model import HAIKU, AnthropicModel, ModelRequest


def text(t, citations=None):
    return NS(type="text", text=t, citations=citations)


def tool(name, **args):
    return NS(type="tool_use", name=name, input=args)


def searched():
    return NS(type="web_search_tool_result")


class FakeMessages:
    def __init__(self, *content) -> None:
        self.content = list(content) or [text("ok")]
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return NS(content=self.content, usage=NS(input_tokens=10, output_tokens=2))


async def ask(*content, **request):
    model = AnthropicModel()
    fake = FakeMessages(*content)
    model._client = NS(messages=fake, api_key="test")
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", **request))
    return response, fake.kwargs


async def test_request_without_tools_omits_the_tools_field():
    # Regression: tools=None was sent as null and the API answered 400 "tools: Input should be a valid array".
    _, kwargs = await ask()
    assert "tools" not in kwargs


async def test_the_providers_search_is_offered_only_when_asked_for_and_is_capped():
    _, kwargs = await ask(search=True, max_searches=1)
    assert kwargs["tools"] == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}]
    _, kwargs = await ask(search=True, max_searches=0)
    assert "tools" not in kwargs


async def test_web_search_is_an_ordinary_function_tool_for_a_role():
    _, kwargs = await ask(tools=["web_search", "fetch"])
    assert [t["name"] for t in kwargs["tools"]] == ["web_search", "fetch"] and all("type" not in t for t in kwargs["tools"])
    assert kwargs["tools"][0]["input_schema"]["required"] == ["query"]


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
    for block, expected in cases:
        response, _ = await ask(block, tools=["fetch"])
        assert response.action == expected


async def test_a_text_only_reply_is_the_answer():
    response, _ = await ask(text("just words"), tools=["plan", "delegate", "answer"])
    assert response.action == AnswerAction(text="just words")


async def test_citations_are_kept_as_source_links_without_duplicates():
    cite = NS(url="https://a.example/x", title="A")
    response, _ = await ask(text("one", [cite]), text(" two", [cite, NS(url="https://b.example", title=None)]))
    answer = response.action.text
    assert answer.startswith("one two")
    assert answer.count("https://a.example/x") == 1
    assert "- [https://b.example](https://b.example)" in answer


async def test_searches_are_counted_and_priced():
    response, _ = await ask(searched(), searched(), text("x"))
    assert response.searches == 2
    assert response.cost_usd > 0.02


async def test_the_files_tool_needs_only_an_operation_and_a_path():
    _, kwargs = await ask(tools=["files"])
    schema = kwargs["tools"][0]["input_schema"]
    assert schema["required"] == ["op", "path"] and set(schema["properties"]) == {"op", "path", "pattern"}
    assert schema["properties"]["op"]["enum"] == ["list", "count", "find"]


async def test_the_browse_tool_and_the_browser_role_in_a_plan():
    _, kwargs = await ask(tools=["browse", "plan"])
    by_name = {t["name"]: t["input_schema"] for t in kwargs["tools"]}
    assert by_name["browse"]["required"] == ["op"] and by_name["browse"]["properties"]["op"]["enum"] == ["open", "click", "more"]
    assert "web_browsing" in by_name["plan"]["properties"]["steps"]["items"]["properties"]["role"]["enum"]


# --- the retry policy's inputs (ADR 0015): the adapter keeps no retries of its own and says what it learned ---


def test_the_sdks_own_retries_are_off():
    assert AnthropicModel()._client.max_retries == 0


def test_a_rate_limit_carries_the_providers_retry_after():
    import anthropic
    import httpx

    from stepout.model import _explain

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, headers={"retry-after": "7"}, request=request)
    failure = _explain(anthropic.RateLimitError("slow down", response=response, body=None))
    assert (failure.kind, failure.status, failure.retry_after) == ("rate_limit", 429, 7.0)

    no_header = httpx.Response(529, request=request)
    assert _explain(anthropic.InternalServerError("busy", response=no_header, body=None)).retry_after is None


async def test_a_reply_reports_the_tokens_it_was_billed_for():
    response, _ = await ask(text("hi"))
    assert (response.input_tokens, response.output_tokens) == (10, 2)


async def test_an_unreadable_reply_says_what_was_wrong_without_the_value_and_keeps_its_cost():
    import pytest

    from stepout.failure import Failure

    with pytest.raises(Failure) as caught:
        await ask(tool("delegate", step="the secret value in the file"))  # `step` must be an integer
    failure = caught.value
    assert failure.kind == "malformed" and failure.cost_usd > 0  # the reply came back, so it was billed
    assert "step" in failure.detail and "secret" not in failure.detail
