---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 7: ProceedScreener is deleted, FixedScreener() does the same
tags: [cleanup,audit,screening,tests]
refs: []
---

**What.** `ProceedScreener` leaves `screening.py`. The audit asked to move it to `tests/support/screeners.py`; it did not need moving: `FixedScreener()` with no script already lets everything through, links nothing and costs nothing (it falls back to `(Proceed(), 0.0)`), so the two test imports use that, and the test that checked the double itself is gone with it.

**Why.** Only tests used it. A class in `src` whose own description says 'the test double' belongs in neither place when an existing double does the job.

**Alternatives.** Moving it as asked: it would keep two doubles that do the same.

**Evidence.** `git grep ProceedScreener` finds nothing in src, tests, scripts or web/mock (the merge agent's scratch scripts outside the repo that import it need `FixedScreener()` from `tests.support.screeners`); offline suite green. Files: `src/stepout/screening.py`, `tests/test_history.py`, `tests/test_screening.py`.
