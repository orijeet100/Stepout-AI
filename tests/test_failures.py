"""What the User sees when the model API fails, at each place a model is called.

The REAL anthropic client over a mock HTTP transport (no network): a fake client would accept anything, which is how the temperature TypeError once
slipped through. Each failure, at the front door, the Orchestrator and a specialist, must give one short plain reply (what happened, what to do),
never a stack trace or an exception name; the Run's row ends `failed` with the cost of the calls that did work; the Ledger keeps the cause; and the
app answers the next message.
"""

import json

import anthropic
import pytest

try:
    import httpx2 as httpx  # the HTTP library anthropic 1.x uses
except ImportError:
    import httpx

from stepout import history
from stepout.app import SavedChannel, run
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import AnthropicModel
from stepout.roles import HAIKU, SONNET
from stepout.runner import Runner
from stepout.screening import HaikuScreener
from stepout.store import Store
from tests.test_history import FakeChannel, NoFetcher, ask


def message(model, *blocks):
    return lambda: httpx.Response(200, json={
        "id": "msg_1", "type": "message", "role": "assistant", "model": model, "stop_reason": "tool_use", "stop_sequence": None,
        "content": list(blocks), "usage": {"input_tokens": 1000, "output_tokens": 500},
    })


def tool(name, **args):
    return {"type": "tool_use", "id": "toolu_1", "name": name, "input": args}


def api_error(status, kind, text="boom"):
    return lambda: httpx.Response(status, json={"type": "error", "error": {"type": kind, "message": text}})


def raises(exc):
    return exc


PROCEED = message(HAIKU, tool("screen", decision="proceed", related=[]))  # the front door lets it through
PLAN = message(SONNET, tool("plan", steps=[{"role": "direct", "goal": "look it up"}]))
ANSWER = message(SONNET, tool("answer", text="Paris."))

# (id, what the API does, words the User's reply must contain, the cause the Ledger keeps)
FAILURES = [
    pytest.param(api_error(429, "rate_limit_error"), ["rate-limiting", "Wait"], "rate_limit", id="429-rate-limit"),
    pytest.param(api_error(529, "overloaded_error"), ["overloaded", "Wait"], "overloaded", id="529-overloaded"),
    pytest.param(api_error(500, "api_error"), ["server error", "Try again"], "server_error", id="500-server-error"),
    pytest.param(api_error(401, "authentication_error"), ["API key", ".env"], "auth", id="401-bad-key"),
    pytest.param(raises(httpx.ReadTimeout("timed out")), ["timed out", "Try again"], "timeout", id="timeout"),
    pytest.param(raises(httpx.ConnectError("no route")), ["Could not reach Anthropic", "internet"], "connection", id="no-network"),
    pytest.param(lambda: httpx.Response(200, text="<html>not json</html>"), ["could not be understood"], "malformed", id="malformed-body-not-json"),
    pytest.param(lambda: httpx.Response(200, json={}), ["could not be understood"], "malformed", id="malformed-body-empty-json"),
    pytest.param(message(SONNET, tool("plan")), ["could not be understood"], "malformed", id="malformed-tool-call"),
    pytest.param(api_error(400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API."), ["out of credit"], "credit", id="400-no-credit"),
]
# Which model call fails: 0 = the front door, 1 = the Orchestrator's first call, 2 = a specialist's first call.
PLACES = [
    pytest.param([], id="front-door"),
    pytest.param([PROCEED], id="orchestrator"),
    pytest.param([PROCEED, PLAN], id="specialist"),
]


class Network:
    """The API as the app sees it: each HTTP request takes the next entry of the script (a response to give, or an exception to raise)."""

    def __init__(self, *script):
        self.script, self.requests = list(script), []

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step()


def real_model(network):
    model = AnthropicModel()
    model._client = anthropic.AsyncAnthropic(api_key="test", max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(network)))
    return model


async def serve(tmp_path, network, *texts, **runner_kwargs):
    """The real app loop: the real front door, Runner and anthropic client, over a fake channel and the mock network. -> the reopened Store."""
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    model = real_model(network)
    saved = SavedChannel(FakeChannel(*[ask("c1", t) for t in texts]), ledger)
    intake = Intake(HaikuScreener(model), ledger, lambda cid: history.exchanges(store, cid))
    await run(saved, intake, Runner(model, NoFetcher(), ledger, saved.send, **runner_kwargs))
    return Store(tmp_path / "t.db")


def replies(store):
    return [m.text for m in history.get_conversation(store, "c1").messages if m.role == "assistant"]


def runs(store):
    return store.query("SELECT outcome, cost_usd FROM runs ORDER BY started_at")


def errors(store):
    return [json.loads(r["data"]) | {"role": r["role"]} for r in store.query("SELECT role, data FROM events WHERE kind = 'error' ORDER BY at, rowid")]


def plain(text):
    assert "Traceback" not in text and "Error" not in text and "Exception" not in text and "httpx" not in text  # no stack trace, no exception class
    assert len(text) < 300 and "\n" not in text.strip()


@pytest.mark.parametrize("failure, words, cause", FAILURES)
@pytest.mark.parametrize("before", PLACES[1:])  # (the front door is a place of its own: it fails open, below)
async def test_a_failed_model_call_gives_a_plain_reply_a_failed_run_and_the_next_message_still_works(tmp_path, before, failure, words, cause):
    network = Network(*before, failure, PROCEED, ANSWER)
    store = await serve(tmp_path, network, "what is the capital of France?", "and of Spain?")

    first, second = replies(store)
    plain(first)
    assert all(w in first for w in words), first
    assert second.startswith("Paris.")  # the app went on serving
    failed, fine = runs(store)
    assert failed["outcome"] == "failed" and fine["outcome"] == "done"
    assert (failed["cost_usd"] > 0) == (len(before) > 0)  # what the calls that worked cost is on the row; a failed call costs nothing
    (error,) = errors(store)
    assert error["cause"] == cause and error["role"] == ("direct" if len(before) == 2 else "orchestrator") and error["summary"] == first
    assert error["type"] and error["type"] not in first  # the cause is in the Ledger, not in the reply


async def test_a_bad_key_at_the_front_door_is_said_once_and_does_not_start_a_run(tmp_path):
    network = Network(api_error(401, "authentication_error"), PROCEED, ANSWER)
    store = await serve(tmp_path, network, "what is the capital of France?", "and of Spain?")

    first, second = replies(store)
    assert "API key" in first and ".env" in first and second.startswith("Paris.")
    assert [r["outcome"] for r in runs(store)] == ["done"]  # the first message never became a Run that would fail the same way
    assert len(network.requests) == 3  # front door; front door; the Orchestrator's one call for the second message... and nothing for the first


@pytest.mark.parametrize("failure", [api_error(429, "rate_limit_error"), api_error(529, "overloaded_error"), api_error(500, "api_error"), raises(httpx.ReadTimeout("t")), lambda: httpx.Response(200, json={})])
async def test_any_other_front_door_failure_still_fails_open(tmp_path, failure):
    network = Network(failure, ANSWER)  # the front door fails; the message goes through to the Orchestrator, which answers
    store = await serve(tmp_path, network, "what is the capital of France?")

    assert replies(store)[0].startswith("Paris.") and [r["outcome"] for r in runs(store)] == ["done"]
    assert [e.kind for e in Ledger(store).query() if e.kind == "screening_fallback"] == ["screening_fallback"]


async def test_no_key_at_all_is_said_plainly_at_first_use(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    model = AnthropicModel()  # the real client with no key: nothing is sent
    saved = SavedChannel(FakeChannel(ask("c1", "hello?")), ledger)
    await run(saved, Intake(HaikuScreener(model), ledger), Runner(model, NoFetcher(), ledger, saved.send))
    (reply,) = replies(Store(tmp_path / "t.db"))
    assert "no Anthropic API key" in reply and ".env" in reply and ".env.example" in reply
    plain(reply)


async def test_an_empty_answer_is_not_shown_as_an_empty_reply(tmp_path):
    network = Network(PROCEED, message(SONNET))  # a 200 with no content at all
    store = await serve(tmp_path, network, "what is the capital of France?")
    (reply,) = replies(store)
    assert reply.strip() and "without an answer" in reply
    assert runs(store)[0]["outcome"] == "failed"


async def test_a_bug_in_a_hand_is_a_plain_failed_run_with_the_cause_in_the_ledger(tmp_path, caplog):
    class Broken:
        async def run(self, *args, **kwargs):
            raise KeyError("lost the thread")

    network = Network(PROCEED, message(SONNET, tool("plan", steps=[{"role": "browser", "goal": "open it"}])), message(SONNET, tool("browse", op="open", url="https://example.com")))
    store = await serve(tmp_path, network, "open example.com", browser=Broken())

    (reply,) = replies(store)
    plain(reply)
    assert "unexpected problem" in reply and "KeyError" not in reply
    assert runs(store)[0]["outcome"] == "failed"
    (error,) = errors(store)
    assert error["cause"] == "internal" and error["type"] == "KeyError" and error["role"] == "browser"
    assert "lost the thread" in caplog.text  # the terminal has the traceback
