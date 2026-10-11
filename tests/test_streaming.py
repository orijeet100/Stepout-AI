"""The reply as it is written: the Anthropic adapter hands the words to the Runner, the Runner sends them out live (never into the Ledger), and a Run
that has read a file sends none, because its finished reply passes through `defang` first and words sent early would not."""

from types import SimpleNamespace as NS

from stepout.domain import AnswerAction
from stepout.model import HAIKU, AnthropicModel, ModelRequest
from tests.support.scripted_model import ScriptedModel
from tests.test_runner import Harness, plan, say
from tests.test_taint_followups import follow_up, x


# --- the adapter ---------------------------------------------------------------------------------------------------------------


class FakeStream:
    def __init__(self, events, final):
        self._events, self._final = events, final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._each()

    async def _each(self):
        for event in self._events:
            yield event

    async def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, events, content):
        self.events, self.final = events, NS(content=content, usage=NS(input_tokens=10, output_tokens=2))
        self.kwargs: dict = {}

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return FakeStream(self.events, self.final)


def start(kind, name=None):
    return NS(type="content_block_start", content_block=NS(type=kind, name=name))


async def streamed(events, content):
    model = AnthropicModel()
    fake = FakeMessages(events, content)
    model._client = NS(messages=fake, api_key="test")
    words: list[str] = []

    async def on_text(w):
        words.append(w)

    response = await model.call(ModelRequest(model=HAIKU, system="s", user_text="u", tools=["answer", "plan"]), on_text=on_text)
    streamed.kwargs = fake.kwargs
    return response, words


async def test_the_answer_tools_text_is_sent_as_it_grows_and_the_reply_is_the_finished_one():
    pieces = ["", '{"te', 'xt": "Hel', "lo wor", 'ld"', "}"]  # the JSON arrives in pieces that fall anywhere
    events = [start("tool_use", "answer")] + [NS(type="input_json", partial_json=p) for p in pieces]
    response, words = await streamed(events, [NS(type="tool_use", name="answer", input={"text": "Hello world"})])
    assert words == ["Hel", "lo wor", "ld"]
    assert response.action == AnswerAction(text="Hello world")


async def test_only_the_answer_tool_asks_for_its_arguments_as_they_are_written():
    await streamed([], [NS(type="text", text="x", citations=None)])
    tools = {t["name"]: t for t in streamed.kwargs["tools"]}
    assert tools["answer"]["eager_input_streaming"] is True and "eager_input_streaming" not in tools["plan"]


def test_a_half_written_string_is_read_as_far_as_it_goes_and_an_escape_waits_for_its_other_half():
    from stepout.model import _partial_text

    def arrived(s):  # what has reached us of {"text": "<s>
        return '{"text": "' + s

    bs = "\\"  # one backslash
    assert _partial_text("") == "" and _partial_text('{"te') == "" and _partial_text(arrived("")) == ""
    assert _partial_text(arrived("Hel")) == "Hel"
    assert _partial_text(arrived("a" + bs)) == "a"  # a lone backslash: the escape is not finished
    assert _partial_text(arrived("a" + bs + "n")) == "a\n"
    assert _partial_text(arrived("say " + bs + '"hi' + bs + '"')) == 'say "hi"'
    assert _partial_text(arrived("caf" + bs + "u00e")) == "caf"  # half a unicode escape
    assert _partial_text(arrived("caf" + bs + "u00e9")) == "café"
    assert _partial_text(arrived(bs + "ud83d")) == ""  # a surrogate pair is whole or not there at all
    assert _partial_text(arrived(bs + "ud83d" + bs + "ude00")) == "\U0001f600"
    assert _partial_text('{"text": "done"} trailing') == "done"  # stops at the closing quote
    assert _partial_text('{"other": "x", "text": "y') == "y"


async def test_the_words_of_a_text_reply_are_sent():
    events = [start("text"), NS(type="text", text="Just ", snapshot="Just "), NS(type="text", text="words", snapshot="Just words")]
    response, words = await streamed(events, [NS(type="text", text="Just words", citations=None)])
    assert words == ["Just ", "words"] and response.action == AnswerAction(text="Just words")


async def test_the_steps_of_a_plan_are_not_sent_as_words():
    events = [start("tool_use", "plan"), NS(type="input_json", partial_json='{"steps": [{"role": "direct", "goal": "g"}]}')]
    _, words = await streamed(events, [NS(type="tool_use", name="plan", input={"steps": [{"role": "direct", "goal": "g"}]})])
    assert words == []


# --- the Runner ----------------------------------------------------------------------------------------------------------------


class Streaming(ScriptedModel):
    """A scripted model that, like the Anthropic adapter, writes its words out before it returns: a lead-in on every call, then the answer's own."""

    streams = True

    async def call(self, request, on_text=None):
        response = await super().call(request)
        if on_text:
            await on_text("hmm ")
            if isinstance(response.action, AnswerAction):
                await on_text(response.action.text)
        return response


def streaming(h, script):
    h.model = h.runner._model = Streaming(script)
    return h


def deltas(h):
    return [(e.role, e.data["text"], e.data.get("reset", False)) for e in h.traced if e.kind == "delta"]


async def test_the_orchestrators_words_go_out_live_and_a_lead_in_before_a_tool_call_is_dropped(tmp_path):
    script = [plan("a"), say("found"), say("The answer.")]
    h = streaming(Harness(tmp_path, script), script)
    await h.run()
    # call 1 (plan): a lead-in, then dropped because the call was a tool call. The Direct agent is not streamed. call 3: the lead-in and the answer.
    assert deltas(h) == [("orchestrator", "hmm ", False), ("orchestrator", "", True), ("orchestrator", "hmm ", False), ("orchestrator", "The answer.", False)]
    assert h.replies[0].text == "The answer."


async def test_the_words_are_live_only_the_ledger_never_sees_them(tmp_path):
    script = [say("Plain.")]
    h = streaming(Harness(tmp_path, script), script)
    task = await h.run()
    assert any(e.kind == "delta" for e in h.traced)
    assert [e for e in h.ledger.query(task.id) if e.kind == "delta"] == []


async def test_a_run_that_has_read_a_file_sends_no_words_early(tmp_path):
    script = [say("From your file.")]
    h = streaming(Harness(tmp_path, script), script)
    await follow_up(h, [x(1, tainted=True)])  # the web is closed from its first step: its reply is filtered before the User sees it
    assert deltas(h) == []
    assert h.replies[0].text == "From your file."


async def test_a_model_that_does_not_stream_is_called_as_before(tmp_path):
    h = Harness(tmp_path, [say("Plain.")])  # ScriptedModel has no `streams` and its `call` takes no `on_text`
    await h.run()
    assert deltas(h) == [] and h.replies[0].text == "Plain."
