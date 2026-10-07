from types import SimpleNamespace as NS

from stepout.domain import AnswerAction, DelegateAction, FetchAction, PlanAction
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
    model._client = NS(messages=fake)
    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", **request))
    return response, fake.kwargs


async def test_request_without_tools_omits_the_tools_field():
    # Regression: tools=None was sent as null and the API answered 400 "tools: Input should be a valid array".
    _, kwargs = await ask()
    assert "tools" not in kwargs


async def test_web_search_is_capped_by_the_remaining_searches():
    _, kwargs = await ask(tools=["web_search", "fetch"], max_searches=2)
    assert [t["name"] for t in kwargs["tools"]] == ["web_search", "fetch"]
    assert kwargs["tools"][0]["max_uses"] == 2


async def test_web_search_is_dropped_once_the_searches_are_used_up():
    _, kwargs = await ask(tools=["web_search", "fetch"], max_searches=0)
    assert [t["name"] for t in kwargs["tools"]] == ["fetch"]


async def test_tool_calls_become_actions():
    steps = [{"role": "direct", "goal": "find the news"}]
    cases = [
        (tool("fetch", url="https://example.com"), FetchAction(url="https://example.com")),
        (tool("plan", steps=steps), PlanAction(steps=steps)),
        (tool("delegate", step=0), DelegateAction(step=0)),
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
