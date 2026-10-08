---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Drop the cost footer
tags: [cost, contract, x2]
refs: [docs/log/2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md, src/stepout/runner.py, src/stepout/channels/cli.py, docs/ui-contract.md]
---

**What.** `Runner.submit` no longer appends `\n\n(cost: $…)` to the reply: the reply's `text` is the Finding's text, and the cost is `Reply.cost_usd` (the Run's total, front door included), which is what the saved assistant message and the contract's `cost_usd` already carry. Ask 1 of [the UI lane's list](2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md). Two consequences handled: (a) **the terminal** printed `reply.text`, so it would have lost the cost; `CliChannel.send` now prints `\n\n(cost: $…)` under a reply that has a non-zero `cost_usd`, which is the same output as before (a decline or chat reply, which used to print no cost, now shows what the front door cost). (b) **Replies saved before this change** still end in the footer in the database. `history.exchanges()` keeps stripping it, so an old reply is not shown to the Orchestrator with a stray cost line; the page keeps its own `splitCostFooter` for the same reason.

**Why.** The footer was a stop-gap ("goes once the page reads `cost_usd`"); U2b's page reads it. The text of a message should be the message.

**Alternatives.** Deleting the footer strip in `history.py`: rejected, saved history still has footers. Doing nothing for the terminal: rejected, it would silently remove the cost display that the CLI User sees today.

**Evidence.** Offline suite **217 passed, 1 skipped, 7 deselected** (215 before; +2 in the new `tests/test_cli.py`). Tests that asserted the footer now assert `text == "Paris"` / `"5"` / `"done"` and `cost_usd` (`test_app`, `test_exchanges`, `test_front_door`). `docs/ui-contract.md` still says the page strips the footer "until then"; that sentence is the UI lane's to update (shared doc, a `contract` entry). Files: `src/stepout/{runner,history}.py`, `src/stepout/channels/cli.py`, `tests/test_{cli,app,exchanges,front_door,history}.py`.
