---
date: 2026-10-08
kind: decision
lane: both
status: accepted
title: tests/test_web_channel.py is rewritten by the UI lane (it tests only channels/web.py)
tags: [ownership,tests,u2]
refs: [tests/test_web_channel.py, scripts/owners.py, docs/plan/README.md]
---

**What.** `tests/test_web_channel.py` was rewritten in U2b. It tests one file, `src/stepout/channels/web.py`, which the UI lane owns, but `tests/` is Main's in `scripts/owners.py` (the default owner), so `python scripts/owners.py --lane ui <branch>` flags this one path. The merge agent should expect that and accept it, or Main adds `("tests/test_web_channel.py", "ui")` to `RULES` and the table in `docs/plan/README.md`.

**Why.** The old tests assert v0 behaviour that v1 changes by design: the first frame is `hello`, a chat is not replayed on connect (history is read over `/api`), trace frames carry ids. They cannot pass beside a v1 channel, and the offline suite must stay green. Three alternatives leave it red or split a channel's tests from its channel.

**Alternatives.** Put the v1 tests under `web/` and leave the old file failing (red suite). Delete the old file and put every test under `web/` (the Main suite then has no test of a channel it ships; and the real-app-loop test needs `tests.*` helpers and the pytest config in `tests/`). Ask Main to rewrite them (Main would be writing UI-contract tests for a file it does not own).

**Evidence.** Seven v0 tests became eighteen; the screenshot-serving and foreign-origin tests were kept as they were. No other file in `tests/` was touched.
