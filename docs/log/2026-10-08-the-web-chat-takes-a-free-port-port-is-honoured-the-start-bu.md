---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: The web chat takes a free port: PORT is honoured, the Start button no longer collides
tags: [run, port, worktree]
refs: [src/stepout/app.py, .claude/launch.json, tests/test_isolation.py, README.md]
---

**What.** `app.web_port()` reads `STEPOUT_PORT`, then `PORT`, then 8765 (an empty value counts as not set). `.claude/launch.json` sets `"autoPort": true` for `stepout-web`, so the desktop app's Start button gives the server a free port in `PORT` when 8765 is taken. README says 8765 is often taken.

**Why.** The User pasted a `.env` into this worktree and pressed Start: `OSError 10048`, port 8765 already in use. The UI lane's mock backend (`web/mock/real_backend.py`) was holding 8765 on purpose (it serves the same port as the real app so the page can be tried without a key). Reproduced: the same command fails with that error while 8765 is held, and `preview_start stepout-web` refused to start. Running on 8770 with the real key was fine (a chat message "What is 2+3?" came back, $0.0077), so the failure was only the collision. Running two checkouts side by side is the normal case in this plan, so the default setup has to cope.

**Alternatives.** Stop the mock servers: they belong to the UI lane's session. A fixed second port in `launch.json`: breaks when that one is taken too. Searching for a free port inside the app: a second port-choosing mechanism where the tool already assigns one.

**Evidence.** `tests/test_isolation.py::test_port_follows_the_preview_tools_port_when_stepout_port_is_not_set` (PORT used, STEPOUT_PORT wins, empty STEPOUT_PORT ignored). By hand: with 8765 held by another process, Start picked 57491 and the page loaded with the earlier chat from this worktree's own `data/stepout.db`. Files: `src/stepout/app.py`, `.claude/launch.json`, `tests/test_isolation.py`, `README.md`.
