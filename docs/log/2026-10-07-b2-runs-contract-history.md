---
date: 2026-10-07
kind: change
lane: main
status: accepted
title: B2 runs contract history
tags: [store, history, contract]
refs: [docs/log/2026-10-07-b2-v0-save-chats.md, docs/ui-contract.md, docs/plan/main-worktree.md, src/stepout/contract.py, src/stepout/history.py]
---

**What.** The rest of B2, after [the v0 slice](2026-10-07-b2-v0-save-chats.md):
1. **`tasks` and `runs` rows** (migration 0004). `Ledger.start_run` saves the Task once and opens a Run row with its budget (`cap_usd`) and start; `end_run` closes it with outcome and cost. Outcomes: `done`; `cancelled` for a Run the User stopped or whose budget ran out (the contract calls both `stopped`; the reason is in the `stop` event); `failed` for an empty answer, a step cap, or a crash (the row is closed even when the model raises).
2. **`Reply` carries `run_id` and `cost_usd`**; the saved assistant message keeps both. The `(cost: $…)` footer stays in the text until the page reads `cost_usd` (X2); dropping it is a one-line change in `Runner.submit` then.
3. **`shot` events carry `url` and `title`**, parsed in the Browse capability from the first two lines of the page view; no caption is invented when the view lacks them.
4. **`src/stepout/contract.py`**: the wire types of `ui-contract.md` v1 as Pydantic models (client frames, `hello`/`message`/`trace`/`status`, conversation list and detail, run summary), with `extra="forbid"` so a field a fixture has and the models lack counts as drift. No shape was changed from the document.
5. **`history.py`** now returns those models: `list_conversations` (with `preview`, the first line of the last message, and `state`), `get_conversation` (messages plus `runs` with `state`, `cost_usd`, `cap_usd`, `steps`, times) and `run_events` (the Run's trace events in order). `state` is what the database knows: idle or running (a Run with no end). `queued` is the live Runner's to add.
6. **`tests/test_contract.py`**: validates every `web/fixtures/*.json` against the models (skips while the folder is empty), accepts the contract's own examples and rejects a stray field, and pins what the Runner emits to the contract's per-kind `data` table.

**Why.** Finish B2 so sync X2 can happen: the page can read chats, runs and events back from the real backend, and the UI lane can build U5.

**Alternatives.** A new `Outcome` member for a budget stop: rejected, "stopped" is a view of `cancelled`. Per-kind `data` models in the contract: rejected, `data` stays a dict (the page ignores unknown keys) and the table is pinned by a test instead. Leaving a crashed Run's row open: rejected, it is closed in `finally`; a process killed mid-Run still leaves an open row (it reads as `running`), and recovering that is B5's `recover()`.

**Assumptions the UI lane should check at X2** (not written into `ui-contract.md`, which is frozen). (a) A fixture is a JSON list of server frames; if the lane prefers another layout, say so in a `contract` entry and the test follows. (b) Optional fields serialize as `null`, not absent (a user message has `"run_id": null`, `"cost_usd": null`); the page's types should allow both. (c) Timestamps serialize as ISO-8601 UTC with `Z`. (d) The web channel must still do its part: send `hello`, validate ids and Host/Origin, build the `status` frame and the queue, and call `history`; `channels/web.py` is not touched here.

**Evidence.** Offline suite **168 passed, 1 skipped (the fixture check, no fixtures yet), 6 deselected** (155 after v0; 135 at the start of the Main lane); every older test unedited except my own v0 history tests, which moved from dicts to models. `tests/test_runs.py`: finished, Stop, spent budget, empty answer and crash each leave the right row; caption present, empty title kept, unreadable view adds nothing. `tests/test_history.py`: the done-when: a scripted browser Run through the app loop, a new `Store` on the same file, and `history` returns the chat, its messages, its Run (done, 4 steps, cost, cap) and every event in order with parents and the screenshot caption; also a stopped Run reads `stopped`, an unended one reads `running`, a 0002 database upgrades through 0004 keeping its events. `tests/test_contract.py`: all five trace kinds (including a refused step and a `stop`) match the table; a bad fixture fails naming its file. By hand: the real CLI app on a fresh database file (`user_version` 4), then a separate process read the chat through `history` as contract JSON. Files: `src/stepout/{contract,history,ledger,runner,domain,app}.py`, `capabilities/browse.py`, `migrations/0004_runs.sql`, `tests/test_{runs,history,contract}.py`.
