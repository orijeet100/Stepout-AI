"""Live eval of the front door: the real Haiku against the labeled prompts. It costs about seven cents, so the default run skips it:

    python -X utf8 -m pytest -m eval -s tests/test_live_screening.py

The merge agent runs it (after telling the User). The bars are proposed (docs/plan/main-worktree.md, B3): after the first run, tune
them in tests/support/screening_eval.py and log the change. `-s` prints every row and what the model decided.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from stepout.model import AnthropicModel
from stepout.screening import HaikuScreener
from tests.support.screening_eval import MAX_FALSE_DECLINES_ON_DEMOS, MAX_MEAN_COST, MIN_AGREEMENT, evaluate, load_rows, summarize

load_dotenv()
pytestmark = [pytest.mark.eval, pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")]


async def test_the_front_door_agrees_with_the_labeled_prompts_cheaply_and_never_declines_a_demo():
    rows = load_rows()
    model = AnthropicModel()
    gate = asyncio.Semaphore(6)

    async def one(row):
        async with gate:
            return (await evaluate(HaikuScreener(model), [row]))[0]  # one screener per row, so its raw answer is that row's

    scored = await asyncio.gather(*(one(r) for r in rows))
    print(f"\n  {'expect':8} {'got':9} {'related':10} {'cost':8} prompt")
    for s in scored:
        mark = "  " if s.agrees else "XX"
        print(f"{mark}{s.row['expect']:8} {s.got:9} {str(s.related):10} ${s.cost:.4f}  {s.row['prompt'][:70]}")
        if not s.agrees:
            print(f"      row wanted {s.row['expect']} {s.row.get('related', '')}; the model said {s.raw}")
    summary = summarize(scored)
    print(f"\n  agreement {summary['agreement']:.0%} (bar {MIN_AGREEMENT:.0%}) · mean cost ${summary['mean_cost']:.4f} (bar ${MAX_MEAN_COST}) · "
          f"false declines {summary['false_declines']} · demo false declines {summary['demo_false_declines']} · fallbacks {summary['fallbacks']}")

    assert len(summary["demo_false_declines"]) <= MAX_FALSE_DECLINES_ON_DEMOS, summary["demo_false_declines"]
    assert summary["agreement"] >= MIN_AGREEMENT
    assert summary["mean_cost"] <= MAX_MEAN_COST
