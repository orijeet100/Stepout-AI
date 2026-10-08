---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 6: one 'unexpected problem' line
tags: [cleanup,audit,failure]
refs: []
---

**What.** The line the User reads when something fails that nobody planned for is `failure.UNEXPECTED`, used by `Runner._failed` and by `app.run`'s last-resort reply. Before, each had its own constant with slightly different words.

**Why.** The merge agent's audit. Two spellings of one message drift apart (they already had: 'could not finish' and 'had to stop this task').

**Alternatives.** Keeping both: the Run's wording ('this task') is right for both places, so it is the one.

**Evidence.** `tests/test_failures.py`, `tests/test_app.py`, `tests/test_runner.py` green (they check the words 'unexpected problem'). Files: `src/stepout/failure.py`, `src/stepout/runner.py`, `src/stepout/app.py`.
