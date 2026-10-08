---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: Merge fix: the declined-request Chrome test no longer races the chat's history load
tags: [merge,e2e,tests]
refs: [web/e2e/test_run_view.py]
---

**What.** `test_a_request_the_gate_declines_has_no_run` counted the page's `.run` elements right after the page loaded, before the open chat's history had arrived, sent the declined message, and compared. When it runs after other tests of the same file, the chat already holds three Runs: `before` read 0, the history then loaded, and the assertion failed with `3 == 0`. It passed alone (an empty chat), so it passed in the UI lane's own runs and failed in the merge agent's, twice in a row. The test now waits for the page to go idle before reading `before` and before reading the count again. No app code changed.

**Why.** A decline starting no Run is a real guarantee worth testing, and a test that is green or red depending on its position in the file is worse than none. The fix is two `wait_for_load_state("networkidle")` lines in a file whose lane was idle at the time.

**Alternatives.** Run each test against a fresh chat (a bigger change to the fixtures, and the shared session is what makes the suite fast). Leave it and run the files separately: hides the race.

**Evidence.** `python -m pytest web/e2e/test_run_view.py` failed (3 passed, 1 failed) before and passes (4 passed) after; the whole Chrome suite then passes in one run: 29 passed.
