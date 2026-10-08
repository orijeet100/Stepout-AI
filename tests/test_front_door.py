"""B3's done-when, offline: the whole loop with the real HaikuScreener over a scripted model, so every model call can be counted and read.

What the live model decides (is this a decline? which exchanges does it link?) is measured by the eval in tests/test_live_screening.py.
These tests pin what the code does with a decision.
"""

import re
from pathlib import Path

import pytest

from stepout import history
from stepout.app import SavedChannel, run
from stepout.domain import AnswerAction
from stepout.intake import Intake
from stepout.ledger import Ledger
from stepout.model import HAIKU, SONNET, ModelResponse, ToolCall
from stepout.runner import Runner
from stepout.screening import HaikuScreener
from stepout.store import Store
from tests.support.scripted_model import ScriptedModel
from tests.test_history import FakeChannel, NoFetcher, ask

SCREEN_COST, STEP_COST = 0.0007, 0.001


def screened(**args):
    return ModelResponse(action=ToolCall(name="screen", input=args), cost_usd=SCREEN_COST)


def proceed(*related):
    return screened(decision="proceed", related=list(related))


def answer(text):
    return ModelResponse(action=AnswerAction(text=text), cost_usd=STEP_COST)


class ModelThatFailsOn(ScriptedModel):
    """Raises on the numbered calls (0-based), as an API outage would."""

    def __init__(self, responses, *fail_on) -> None:
        super().__init__(responses)
        self._fail_on = set(fail_on)

    async def call(self, request):
        if len(self.requests) in self._fail_on:
            self.requests.append(request)
            raise RuntimeError("API down")
        return await super().call(request)


async def converse(tmp_path, messages, script, model=None):
    """The real app loop; the screener and the Runner share one scripted model, so `model.requests` is every call in order."""
    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    model = model or ScriptedModel(script)
    channel = FakeChannel(*messages)
    saved = SavedChannel(channel, ledger)
    intake = Intake(HaikuScreener(model), ledger, lambda cid: history.exchanges(store, cid))
    await run(saved, intake, Runner(model, NoFetcher(), ledger, saved.send))
    return model, channel, Store(tmp_path / "t.db")


async def test_a_decline_costs_one_haiku_call_and_no_orchestrator_call(tmp_path):
    decline = screened(decision="decline", reply="That means paying someone.", alternative="I can look things up.")
    model, channel, store = await converse(tmp_path, [ask("c1", "pay my landlord $200")], [decline])

    assert [r.model for r in model.requests] == [HAIKU]
    assert [(r.text, r.cost_usd, r.run_id) for r in channel.sent] == [("That means paying someone. I can look things up.", SCREEN_COST, None)]
    assert store.query("SELECT COUNT(*) FROM runs")[0][0] == 0 and store.query("SELECT COUNT(*) FROM events WHERE kind = 'step'")[0][0] == 0
    (event,) = store.query("SELECT cost_usd, data FROM events WHERE kind = 'screening'")
    assert event["cost_usd"] == pytest.approx(SCREEN_COST) and '"decision": "decline"' in event["data"]
    saved = history.get_conversation(store, "c1").messages[-1]
    assert (saved.role, saved.cost_usd) == ("assistant", pytest.approx(SCREEN_COST))  # the User can see what the decline cost


async def test_a_chat_reply_costs_one_haiku_call_and_no_orchestrator_call(tmp_path):
    model, channel, store = await converse(tmp_path, [ask("c1", "hi!")], [screened(decision="chat", chat_kind="greeting", reply="Hello! I can search the web and read pages.", related=[])])
    assert [r.model for r in model.requests] == [HAIKU]
    assert [(r.text, r.cost_usd) for r in channel.sent] == [("Hello! I can search the web and read pages.", SCREEN_COST)]
    assert store.query("SELECT COUNT(*) FROM runs")[0][0] == 0


async def test_a_slash_command_never_reaches_the_front_door(tmp_path):
    model, channel, _ = await converse(tmp_path, [ask("c1", "/help")], [])
    assert model.requests == [] and channel.sent[0].text == "Unknown command: /help"


FOUR_CHATS = [
    ask("c1", "what does example.com say?"),
    ask("c1", "what is 2+3?"),
    ask("c1", "list the PDFs on D:"),
]


async def test_related_exchanges_reach_the_orchestrator_in_full_and_a_new_task_gets_none(tmp_path):
    script = [proceed(), answer("It says Example Domain."), proceed(), answer("5"), proceed(), answer("Three: a, b, c."), proceed(1, 3), answer("Done.")]
    model, _, _ = await converse(tmp_path, [*FOUR_CHATS, ask("c1", "and that first site again, plus the PDFs")], script)

    orchestrator = [r for r in model.requests if r.model == SONNET]
    assert all("Previous exchanges" not in r.user_text for r in orchestrator[:3])  # three new Tasks: no history
    last = orchestrator[3].user_text
    assert "#1\nrequest: what does example.com say?\nreply: It says Example Domain." in last
    assert "#3\nrequest: list the PDFs on D:\nreply: Three: a, b, c." in last
    assert "what is 2+3?" not in last  # linked 1 and 3, not 2
    screener_view = model.requests[6].user_text  # what the front door was shown for the 4th message
    for line in ('#1 "what does example.com say?" -> It says Example Domain.', '#2 "what is 2+3?" -> 5', '#3 "list the PDFs on D:" -> Three: a, b, c.'):
        assert line in screener_view  # it was shown all three, one line each, with their numbers


async def test_website_then_something_random_then_the_website_again_links_back_to_the_website(tmp_path):
    script = [proceed(), answer("It says Example Domain."), proceed(), answer("5"), proceed(1), answer("Same as before.")]
    model, _, _ = await converse(tmp_path, [FOUR_CHATS[0], FOUR_CHATS[1], ask("c1", "check that website again")], script)
    last = [r for r in model.requests if r.model == SONNET][2].user_text
    assert "reply: It says Example Domain." in last and "what is 2+3?" not in last  # a link across the unrelated message in between


async def test_a_failed_call_proceeds_with_the_last_three_exchanges_and_records_it(tmp_path):
    script = [proceed(), answer("A1"), proceed(), answer("A2"), proceed(), answer("A3"), proceed(), answer("A4"), answer("final")]
    four = [ask("c1", f"question {n}") for n in (1, 2, 3, 4)]
    model, channel, store = await converse(tmp_path, [*four, ask("c1", "go on")], script, ModelThatFailsOn(script, 8))  # call 8 = the 5th screening

    orchestrator = [r for r in model.requests if r.model == SONNET][4].user_text
    assert all(f"#{n}\n" in orchestrator for n in (2, 3, 4)) and "#1\n" not in orchestrator  # the last three
    (event,) = store.query("SELECT conversation_id, data FROM events WHERE kind = 'screening_fallback'")
    assert event["conversation_id"] == "c1" and '"failure": "RuntimeError"' in event["data"]
    assert channel.sent[-1].text.startswith("final")  # the message was served, not lost


async def test_an_answer_in_words_instead_of_the_tool_also_falls_back_and_its_cost_still_counts(tmp_path):
    script = [proceed(), answer("A1"), ModelResponse(action=AnswerAction(text="Sure, go ahead!"), cost_usd=SCREEN_COST), answer("final")]
    model, channel, store = await converse(tmp_path, [ask("c1", "first"), ask("c1", "go on")], script)
    assert "#1\n" in [r for r in model.requests if r.model == SONNET][1].user_text
    assert store.query("SELECT COUNT(*) FROM events WHERE kind = 'screening_fallback'")[0][0] == 1
    assert channel.sent[-1].cost_usd == pytest.approx(SCREEN_COST + STEP_COST)


async def test_the_front_doors_cost_is_part_of_the_runs_total_and_its_record(tmp_path):
    _, channel, store = await converse(tmp_path, [ask("c1", "what is 2+3?")], [proceed(), answer("5")])
    assert channel.sent[0].text == "5" and channel.sent[0].cost_usd == pytest.approx(SCREEN_COST + STEP_COST)
    assert store.query("SELECT cost_usd FROM runs")[0]["cost_usd"] == pytest.approx(SCREEN_COST + STEP_COST)
    assert store.query("SELECT cost_usd FROM events WHERE kind = 'screening'")[0]["cost_usd"] == pytest.approx(SCREEN_COST)


def test_route_is_gone_from_the_source():
    src = Path(__file__).resolve().parents[1] / "src"
    hits = [f"{p.relative_to(src)}:{n}" for p in src.rglob("*") if p.suffix in (".py", ".md") for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if re.search(r"\bRoute\b", line)]
    assert hits == []


async def test_a_question_the_front_door_tried_to_answer_itself_still_reaches_the_orchestrator(tmp_path):
    tried = screened(decision="chat", reply="51", related=[])  # no chat_kind: this is not a greeting, thanks or a question about the assistant
    model, channel, store = await converse(tmp_path, [ask("c1", "What is 17 times 3?")], [tried, answer("51")])
    assert [r.model for r in model.requests] == [HAIKU, SONNET]  # the Orchestrator answered, not the front door
    assert channel.sent[0].text == "51" and channel.sent[0].run_id and store.query("SELECT COUNT(*) FROM runs")[0][0] == 1
    assert store.query("SELECT COUNT(*) FROM events WHERE kind = 'screening_fallback'")[0][0] == 0  # a downgrade is not a failure


async def test_a_follow_up_the_front_door_tried_to_answer_from_its_index_gets_its_history(tmp_path):
    tried = screened(decision="chat", chat_kind="about_assistant", reply="Those events are free.", related=[1])  # it pointed at exchange 1
    script = [proceed(), answer("Listed 14 events from luma.com/tech."), tried, answer("Six of them are free.")]
    model, channel, _ = await converse(tmp_path, [ask("c1", "list Luma tech events"), ask("c1", "which of those events are free?")], script)
    second = [r for r in model.requests if r.model == SONNET][1].user_text
    assert "#1\nrequest: list Luma tech events\nreply: Listed 14 events from luma.com/tech." in second  # the real Orchestrator sees the real history
    assert channel.sent[-1].text == "Six of them are free."
