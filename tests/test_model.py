from types import SimpleNamespace

from stepout.model import HAIKU, AnthropicModel, ModelRequest


class _FakeMessages:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="lookup")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        )


def _model() -> tuple[AnthropicModel, _FakeMessages]:
    model = AnthropicModel()
    fake = _FakeMessages()
    model._client = SimpleNamespace(messages=fake)
    return model, fake


async def test_request_without_tools_omits_the_tools_field():
    # Regression: tools=None was sent as null and the API answered 400 "tools: Input should be a valid array".
    model, fake = _model()
    await model.call(ModelRequest(model=HAIKU, system="s", user_text="what is 1+2"))
    assert "tools" not in fake.kwargs


async def test_request_with_tools_sends_them():
    model, fake = _model()
    await model.call(ModelRequest(model=HAIKU, system="s", user_text="news", tools=True))
    assert [t["name"] for t in fake.kwargs["tools"]] == ["web_search", "fetch"]
