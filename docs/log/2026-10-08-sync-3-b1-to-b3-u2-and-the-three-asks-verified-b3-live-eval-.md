---
date: 2026-10-08
kind: note
lane: both
status: accepted
title: Sync 3: B1 to B3, U2 and the three asks verified; B3 live eval is below its bars
tags: [sync,b3,eval]
refs: [docs/plan/README.md, docs/log/2026-10-08-merge-fix-web-mock-real-backend-py-follows-the-b3-api-and-a-.md, docs/log/2026-10-07-b3-front-door.md, tests/test_live_screening.py]
---

**What.** The merge agent's third pass, on the scratch branch `integrate`: B3 (+ its `tests/data` fix), U2a, U2b and the Main lane's three asks from the U2b contract entry (cost footer dropped, a message keeps its own id and time, `app.py` gives `WebChannel` its history). `main` was moved to `sync-2` (B1 + U1 + B2) earlier and has **not** moved again: B3 does not pass its live bars.

**Passed.** Offline suite 233 passed, 0 skipped (no local-only files); contract tests with the UI lane's 7 fixtures; web: 36 vitest, lint, build, contrast; `web/mock` 10 passed; log check and the Main lane's ownership check. Live smoke suite 6/6, $0.112 (sync 2: $0.117). A 49-check attack and protocol probe of the real v1 channel (Host, Origin, content type, ids, paths, oversized and malformed frames, restart). A real-model end-to-end probe over v1, with Chrome, through a server restart: every proceed made a Run and every chat or decline did not; the front door's cost is inside the Run's cost, counted once (ledger = runs + chat/decline screenings); the ids streamed live equal the ids saved in history; screenshots are served as images with `url` and `title`; follow-ups linked ([1], then [1,2] after the restart); $0.065. The real page on the real backend in a browser: chats list, send, reply, survive a server kill. The real `data/stepout.db` upgrades 2 to 5 with all 234 events kept (tested on a copy first; a backup was made before the real upgrade).

**Failed or open.**
1. **B3 live eval: agreement 71% (bar 90%)**, mean cost $0.0016 (bar $0.003, met), 1 demo false decline, 1 fallback. The pattern: ordinary questions (17 times 3, the capital of France, "explain how transformers work") are answered by the front door as `chat`, and so are two that depend on the chat's history ("which of those events are free?"), which the chat reply cannot see. Two false declines: "summarize this article about password managers" and a `.env` request labelled `proceed` (a decline there is safe; whether it should count as a false decline is the User's call). Handed to the Main lane; the merge agent re-runs the 63 prompts after the change (about $0.10).
2. **`scripts/owners.py --lane ui` flags `tests/test_web_channel.py`** (tests/ is Main's). The UI lane logged why: it tests only the UI-owned channel. Not changed by the merge agent; pending the User's decision (add `("tests/test_web_channel.py", "ui")` to the rules and the plan table).
3. **`web/mock/real_backend.py` was broken by B3** (the UI lane could not see the new API from its branch). Fixed on `integrate` with a test: see the linked change entry.
4. The live eval cost about $0.10, not the $0.07 estimated; this sync spent about $0.28 in total (smoke $0.112, eval about $0.10, probe $0.065).

**Why.** Recorded so the next pass starts from facts: what passed, what did not, and who owns each open item.

**Alternatives.** Moving `main` past `sync-2` anyway: rejected, B3 is a Main-lane feature that fails its own proposed bars and a failing front door answers history-dependent follow-ups without the history.

**Evidence.** The commands: `pytest -q`, `pytest tests/test_contract.py web/mock`, `npm test/lint/build/check:contrast` in `web/`, `scripts/log.py check --range main..HEAD`, `scripts/owners.py --lane main|ui <branch>`, `pytest -m eval -s tests/test_live.py` and `tests/test_live_screening.py`; the probes were run from the merge agent's scratch directory and are not committed.
