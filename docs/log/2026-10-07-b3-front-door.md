---
date: 2026-10-07
kind: change
lane: main
status: accepted
title: B3 front door
tags: [intake, screening, exchanges]
refs: [docs/log/2026-10-07-front-door-v0-one-haiku-call.md, docs/log/2026-10-07-follow-ups-link-to-exchanges.md, docs/plan/main-worktree.md]
---

**What.** In progress (slice 2 of 5). Done: `Exchange` and `history.exchanges()`; the Orchestrator-only history block; the front door's cost counted in the Run (it starts the Run's spend, so the $1 cap, the reply total and `runs.cost_usd` include it); `ModelRequest.tool_defs` and `ToolCall` (a one-off tool the caller supplies, so `model.py` gains no hard-coded tool); `screening.py` with `Screener`, `HaikuScreener` and `ProceedScreener`. Still to do: switch Intake over and delete Route and the regex gate, the 50-prompt set, docs. The final text is written when B3 is done.

**Why.** [Front door v0 is one Haiku call](2026-10-07-front-door-v0-one-haiku-call.md); [a follow-up links to earlier exchanges](2026-10-07-follow-ups-link-to-exchanges.md).

**Alternatives.** See those entries.

**Evidence.** To be filled in at the end of B3.
