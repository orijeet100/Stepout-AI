---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: app.py gives WebChannel its history
tags: [history, web, x2]
refs: [docs/log/2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md, src/stepout/app.py, src/stepout/channels/web.py]
---

**What.** Ask 3 of [the UI lane's list](2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md). In web mode `app.main` builds `WebChannel(port=…, shots=…, history=StoreHistory(store))`, so the channel reads chats, runs and events through the app's own `Store` instead of opening a second connection to `data/stepout.db` through its `DEFAULT_DB` fallback. `StoreHistory` and the `history=` argument are in the UI lane's `channels/web.py` (U2b), which is **not on this branch**, so the import is inside the web branch of `main()` (marked `ponytail`): this tree still imports, tests run, and the terminal mode is untouched. **This line works only in a tree that has U2b, that is, after the merge.** On this branch alone `python -m stepout.app web` would fail with an unexpected-argument error until the merge brings in U2b; the merged result is what is verified below. When U2b is on `main`, the import moves to the top beside `WebChannel`.

**Why.** A second SQLite connection to the same file is a workaround; one Store is the design (ADR 0006). With `history=` given, the channel's fallback path is never used, and the UI lane can delete `DEFAULT_DB`.

**Alternatives.** Waiting until U2b reaches `main` to make the change: rejected, it was asked for now, it is one line, and the merge is where the two halves meet. A try/except around the import: rejected, dead code after the merge. Moving `StoreHistory` into Main's `history.py`: it is the UI lane's class in the UI lane's file; not mine to move.

**Evidence.** The offline suite on this branch alone: **221 passed, 1 skipped, 7 deselected** (the three asks together: +6 tests over the 215 before them). The combination was checked in a throwaway clone (since deleted): this branch plus the UI branch `e6ab524` merged with **no conflicts** (`docs/STATUS.md` auto-merged), and in that tree **233 passed, 7 deselected, nothing skipped**. The fixture check, which skips on this branch alone, ran and passed against the UI lane's real `web/fixtures`, and the UI lane's own web channel tests pass with the changes from asks 1 and 2. Then the real `python -m stepout.app web` (dummy key, no model call) was started from that merged tree with the channel's fallback path pointed at a folder that must never be created: a chat seeded into the app's database from another process came back from `GET /api/conversations` (`200`, `c1`, `idle`) and the fallback folder was **not** created. The same probe with this one line reversed created the fallback folder (a second Store was opened) and returned `[]`, so the probe does tell the two apart. Files: `src/stepout/app.py`.
