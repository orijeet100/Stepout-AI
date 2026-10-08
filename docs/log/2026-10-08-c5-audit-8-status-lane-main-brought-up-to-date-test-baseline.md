---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 8: STATUS Lane: Main brought up to date; test baselines say 'all tests pass'
tags: [cleanup,audit,docs]
refs: []
---

**What.** The B3 row of STATUS says the front door passed its live eval (97%, two stable runs at temperature 0, sync 4) instead of 'first live eval FAILED ... re-run pending'; the C1 row's 'live re-run pending' says passed; the offline test count is 488; `docs/plan/README.md` and `docs/plan/main-worktree.md` no longer pin a count of 135 tests, they say all tests pass. C3 and C4 rows and the code map (`scripts/acceptance.py`, `links.py`, `failure.py`) were updated with their slices.

**Why.** The merge agent's audit found the Main lane's own section lagging behind the live results it had recorded elsewhere, and two baselines that were true on 2026-10-07 and had been wrong ever since.

**Alternatives.** A count that is updated every cycle: it is the first number to go stale; 'all tests pass' is the claim that matters.

**Evidence.** Docs only. Offline suite 488 passed. The audit's last item (`_now()` defined twice, in `domain.py` and `channels/web.py`) is left: the channel is the UI lane's, and the merge agent will raise it with them. Files: `docs/STATUS.md`, `docs/plan/README.md`, `docs/plan/main-worktree.md`.
