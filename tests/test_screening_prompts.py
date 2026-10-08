"""The labeled prompt set is sound, and the scoring that the live eval relies on works (offline)."""

from pathlib import Path

import pytest

from stepout.domain import ChatReply, Decline, Proceed
from tests.support.screening_eval import evaluate, exchanges_of, load_rows, summarize

LOG = Path(__file__).resolve().parents[1] / "docs" / "log" / "2026-10-07-front-door-v0-one-haiku-call.md"
ROWS = load_rows()


def test_the_set_is_well_formed_and_covers_every_kind_of_decision():
    assert len(ROWS) >= 50
    assert len({r["prompt"] + str(r.get("history")) for r in ROWS}) == len(ROWS)  # no duplicates
    for r in ROWS:
        assert r["prompt"].strip() and r["expect"] in ("decline", "chat", "proceed") and r["tag"], r
        if "related" in r:  # only a Follow-up that proceeds links anything, to exchanges that exist
            assert r["expect"] == "proceed" and r.get("history"), r
            assert all(isinstance(n, int) and 1 <= n <= len(r["history"]) for n in r["related"]), r
    kinds = [r["expect"] for r in ROWS]
    assert kinds.count("decline") >= 8 and kinds.count("chat") >= 4 and kinds.count("proceed") >= 25
    assert any(r.get("related") == [] for r in ROWS) and any(len(r.get("related", [])) >= 2 for r in ROWS)  # "links nothing" and "links two" are both tested


def test_the_demo_queries_are_all_expected_to_proceed():
    demos = [r for r in ROWS if r["tag"] == "demo"]
    assert len(demos) >= 9 and all(r["expect"] == "proceed" for r in demos)


def test_the_probe_prompts_are_exactly_the_ones_the_log_records():
    probe = [r for r in ROWS if r["tag"] == "probe"]
    assert len(probe) == 11  # the 7 false declines and the 4 named misses
    log = LOG.read_text(encoding="utf-8")
    assert all(f"`{r['prompt']}`" in log for r in probe)  # copied from the entry, not paraphrased
    assert {r["expect"] for r in probe if r["prompt"] in ("send $200 to my landlord", "wire money to John", "write me a python script", "close my bank account")} == {"decline"}
    assert sum(r["expect"] == "proceed" for r in probe) == 7


def test_nothing_in_the_set_is_a_real_path_or_name_from_the_users_machine():
    text = Path(__file__).resolve().parents[1].joinpath("tests", "data", "screening_prompts.jsonl").read_text(encoding="utf-8").lower()
    assert "orije" not in text and "manasvin" not in text


# --- the scoring itself ---------------------------------------------------------------------------------------------------


class Oracle:
    """Answers every row as labeled, and checks it was shown the right history."""

    def __init__(self, rows):
        self._by_prompt = {r["prompt"] + str(r.get("history")): r for r in rows}

    async def screen(self, text, recent):
        (row,) = [r for r in self._by_prompt.values() if r["prompt"] == text and [x.id for x in exchanges_of(r)] == [x.id for x in recent]]
        match row["expect"]:
            case "decline":
                return Decline(reason="no", alternative="yes"), 0.001
            case "chat":
                return ChatReply(text="hi"), 0.001
            case _:
                return Proceed(related=row.get("related", [])), 0.001


class Constant:
    def __init__(self, answer, cost=0.002):
        self._answer, self._cost = answer, cost

    async def screen(self, text, recent):
        return self._answer, self._cost


async def test_a_screener_that_answers_as_labeled_scores_perfectly():
    summary = summarize(await evaluate(Oracle(ROWS), ROWS))
    assert summary["agreement"] == 1.0 and summary["false_declines"] == [] and summary["fallbacks"] == []
    assert summary["mean_cost"] == pytest.approx(0.001)


async def test_declining_everything_is_caught_as_false_declines_on_the_demos():
    summary = summarize(await evaluate(Constant(Decline(reason="no", alternative="yes")), ROWS))
    assert len(summary["demo_false_declines"]) == sum(r["tag"] == "demo" for r in ROWS)
    assert summary["agreement"] == pytest.approx(sum(r["expect"] == "decline" for r in ROWS) / len(ROWS))


async def test_letting_everything_through_never_false_declines_but_misses_declines_chat_and_links():
    summary = summarize(await evaluate(Constant(Proceed()), ROWS))
    assert summary["false_declines"] == [] and summary["agreement"] < 0.8
    linked = [s for s in await evaluate(Constant(Proceed()), ROWS) if "related" in s.row and s.row["related"]]
    assert linked and not any(s.agrees for s in linked)  # "links nothing" is wrong for a message that depends on an earlier exchange


async def test_a_wrong_link_is_a_disagreement_even_when_the_decision_is_right():
    follow_up = [r for r in ROWS if r.get("related") == [1]][:1]
    (right,) = await evaluate(Constant(Proceed(related=[1])), follow_up)
    (wrong,) = await evaluate(Constant(Proceed(related=[2])), follow_up)
    assert right.agrees and not wrong.agrees


async def test_an_unusable_answer_counts_as_a_fallback_and_a_disagreement():
    scored = await evaluate(Constant(None), ROWS)
    assert summarize(scored)["fallbacks"] == [r["prompt"] for r in ROWS] and not any(s.agrees for s in scored)
