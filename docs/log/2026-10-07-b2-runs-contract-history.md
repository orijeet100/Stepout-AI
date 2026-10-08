---
date: 2026-10-07
kind: change
lane: main
status: accepted
title: B2 runs contract history
tags: [store, history, contract]
refs: [docs/log/2026-10-07-b2-v0-save-chats.md, docs/ui-contract.md, docs/plan/main-worktree.md]
---

**What.** In progress; the final text is written when B2 is done. Done so far: (1) `tasks` and `runs` rows (migration 0004): `Ledger.start_run` saves the Task once and opens a Run row with its budget (`cap_usd`) and start; `end_run` closes it with the outcome and cost. Outcomes: `done`; `cancelled` for a Run the User stopped or whose budget ran out (the contract calls both `stopped`; the reason is in the `stop` event); `failed` for an empty answer, a step cap, or a crash (the row is closed even when the model raises). (2) `Reply` carries `run_id` and `cost_usd`; the saved assistant message keeps both; the `(cost: $…)` footer stays in the text until the page reads `cost_usd` (X2). (3) A `shot` event's data gains `url` and `title`, parsed in the Browse capability from the first two lines of the page view; no caption is invented when the view lacks them.

**Why.** Finish B2 after the v0 slice: [B2 v0 save chats](2026-10-07-b2-v0-save-chats.md).

**Alternatives.** Outcome for a budget stop: a new `Outcome` member was rejected (the enum is the domain's seven outcomes, and "stopped" is a view of cancelled). A crash that leaves a Run row open forever was rejected: the row is closed in `finally`. A process killed mid-Run still leaves an open row; recovering that is B5's `recover()`.

**Evidence.** Offline suite 162 passed, 6 deselected after these three slices. `tests/test_runs.py`: finished, Stop, spent budget, empty answer and crash each leave the right row; a saved answer links to its `runs` row and cost; the caption is present, an empty title is kept, and an unreadable view adds nothing. Still to do in this entry: `contract.py`, `history.py` returning its models with `run_events`, `tests/test_contract.py`.
