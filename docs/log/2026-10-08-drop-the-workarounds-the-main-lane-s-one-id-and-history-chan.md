---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: Drop the workarounds the Main lane's one-id and history changes made unnecessary
tags: [cleanup,channel,x2]
refs: [src/stepout/channels/web.py, web/src/store.ts, tests/test_web_channel.py, docs/log/2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md]
---

**What.** The Main lane did two of the three asks in [the U2b contract entry](2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md): a saved message keeps the `id` and `at` of the live one (`Message`, `Reply`), and `app.py` passes `history=StoreHistory(store)`. So: (1) `WebChannel.send` uses `reply.id` and `reply.at` and the saved-copy lookup (`_saved_copy`, which read a whole chat per reply) is deleted; (2) `history=` is now a required keyword of `WebChannel`, and the fallback that opened a second `Store` (`DEFAULT_DB`, `_reader`) is deleted; (3) the page merges a chat read back from history by id again, and the rule "keep only live messages newer than history" is deleted. The cost-footer shim `splitCostFooter` stays: it still strips the footer from messages saved before the footer was dropped.

**Why.** Each was a workaround for something Main has now fixed; less code and one fewer way for a live message and its saved copy to differ.

**Alternatives.** Keeping the lookups "just in case" (they hide a regression of the one-id rule instead of failing on it).

**Evidence.** The real-app-loop test now asserts that both your echoed message and the reply have the same `id` and `at` as their saved copies. `python -m pytest tests/test_web_channel.py web/mock`: 28 passed; `npm test`: 36 passed; build and lint clean.
