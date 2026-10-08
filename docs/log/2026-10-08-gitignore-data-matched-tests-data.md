---
date: 2026-10-08
kind: note
lane: main
status: accepted
title: gitignore data matched tests data
tags: [gitignore, tests]
refs: [.gitignore, tests/data/screening_prompts.jsonl, docs/log/2026-10-07-b3-front-door.md]
---

**What.** `.gitignore` line 5, `data/` (the Assistant's local state: database, grants, run folders), also matches `tests/data/`. B3's `tests/data/screening_prompts.jsonl` was therefore never committed: `git add tests` skipped it without a word, and every local run passed because the file was on disk. A fresh checkout failed at collection in `tests/test_screening_prompts.py`. The merge agent found it. Fixed with `!tests/data/` under `data/`; the file is now tracked.

**Why.** The negation re-includes only `tests/data/`; the root `data/` and any other `data/` folder (`web/data`, `src/stepout/data`) stay ignored as before. Anchoring `/data/` would have un-ignored those too.

**Alternatives.** `git add -f` alone: fixes this file but not the next test data file. `/data/`: wider than needed.

**Evidence.** `git check-ignore -v tests/data/screening_prompts.jsonl` now finds nothing; `git status --ignored --short tests/data` lists no ignored entry; `data/x`, `web/data/x` and `src/stepout/data/x` are still ignored. A fresh clone of the branch at `2095a0c` has the file tracked (63 lines), collects 216 tests and passes 215 (1 skipped, 7 deselected: the paid ones). The same clone at the previous commit `07f45d1` has no `tests/data` and fails collecting `tests/test_screening_prompts.py`, so the check does catch the problem. **Lesson for the checklist:** after adding files, `git status --short` shows what is staged but never what was ignored; `git status --ignored --short | grep '^!!'` does. A new test data file under `tests/data/` is now safe to add.
