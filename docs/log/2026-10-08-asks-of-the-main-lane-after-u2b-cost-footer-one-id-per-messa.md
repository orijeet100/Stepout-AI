---
date: 2026-10-08
kind: contract
lane: both
status: accepted
title: Asks of the Main lane after U2b: cost footer, one id per message, pass history to the channel
tags: [contract,x2]
refs: [src/stepout/runner.py, src/stepout/ledger.py, src/stepout/app.py, src/stepout/channels/web.py, docs/ui-contract.md]
---

**What.** Three small changes the UI lane cannot make (they are in Main's files). None changes a wire shape; the page and the channel work without them, and each one removes a workaround.

1. **Drop the cost footer.** In `Runner.submit` the line `reply = f"{finding.text}\n\n(cost: ${run.spent:.4f})"` (it says "the footer goes once the page reads `cost_usd` (X2)") can become `reply = finding.text`. The page reads `cost_usd` from the message and shows it itself. Until then the page strips the footer in one function, `splitCostFooter` in `web/src/protocol.ts`; messages saved before the change keep their footer in the database, and that function keeps handling them, so it stays.
2. **One id and time per message.** `Ledger.save_message(conversation_id, role, text, run_id, cost_usd)` makes its own event id and time and returns nothing, so a live `message` frame and the saved copy cannot have the same id. For an assistant reply the channel now looks the saved copy up (`WebChannel._saved_copy`, which reads the whole chat). For a user message it cannot: the echo goes out before `SavedChannel` saves it, so the page treats history as the record and keeps only live messages newer than anything history has. Ask: `save_message` takes `id` and `at` (and `SavedChannel` passes the incoming `Message.id` and `Message.at`, and gives the reply one), or returns the saved event. Then both lookups go.
3. **Give the channel its history.** `app.py` builds `WebChannel(port=…, shots=…)` and the channel opens its own second `Store` on `data/stepout.db` (`DEFAULT_DB` in `channels/web.py`, a copy of `DB_PATH`). Ask: `WebChannel(port=…, shots=…, history=StoreHistory(store))` (`StoreHistory` is in `channels/web.py`); then the default goes.

**Also for Main to know** (not asks): B5's `recover()` closes Runs a crash left open. Until then the channel reports such a Run as `failed` when a chat is read back, so a crashed Run is not shown as running forever. And `docs/ui-contract.md` has a new "Notes from U2b" section that says how the channel fills in what v1 left open (`status` while a message is being screened, queued messages, `POST /api/conversations`, the default chat). That section is documentation of behaviour, not a new field.

**Why.** Each one is a workaround today: the footer is stripped by the page, two id lookups are heuristics, and a second connection to the same SQLite file is opened.

**Alternatives.** The UI lane editing `runner.py`, `ledger.py` and `app.py` itself (not its files; `owners.py` would flag them).

**Evidence.** The workarounds and their tests: `splitCostFooter` (`web/src/protocol.test.ts`), `_saved_copy` (`tests/test_web_channel.py`, the last test), the history rule in `web/src/store.ts` (`store.test.ts`), `StoreHistory` and `DEFAULT_DB`.
