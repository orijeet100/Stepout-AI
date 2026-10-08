---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Two efficiency fixes from the live C2 run: skipped repeats are marked and shrunk pages may be re-opened; no reader step before its path is known
tags: [runner, browser, prompt, cost]
refs: [docs/plan/v0-finish.md, src/stepout/runner.py, src/stepout/roles.py, tests/test_run_efficiency.py, tests/test_reader_demos.py]
---

**What.** The merge agent's live run of the two Reader demos showed two kinds of waste. Both are fixed at their cause.

1. **Browse `open` of the same page, "allowed" four times (about $0.06).** Reproduced with the scripted model (open, click 30, more, more, then open again three times): the repeat guard *did* keep the page from loading again (the hand was called 4 times, not 7), but a skipped repeat was recorded as an ordinary allowed step with a full model call's cost, so the Trace looked like four page loads. And the model asked again for a reason: `browse` keeps only the newest two page views in full, so after a click and two `more` the first view was a one-line stub, the model wanted the posting back, and the guard's "the result will not change" was true but useless to it. Now:
   - the guard refuses a repeat only while the earlier result is still in the Role's notes unchanged; if it has shrunk, running it again is allowed (a page load, not a wasted model call that ends in a refusal);
   - a skipped repeat is recorded as such: the step's summary reads `repeat, not run again: browse open <url>` and its data carries `repeat: true` (the verdict stays `allow`: the Gate had nothing against it). The acceptance harness counts these.
2. **A Reader step planned before its path was known (9 steps for a 4-step job).** The Orchestrator wrote `files: list; reader: read ...` in one plan, and a specialist sees only its own goal, so the Reader had no path. The prompt now says it outright: a reader step needs the exact path in its goal; if it does not have it yet, plan only the files step, plan the reader step after that Finding is in, and never plan both in one plan. (C2's wording was a clause inside the re-plan rule, which the model did not take as a prohibition.)

**Measured, offline.** The cheapest honest flow is pinned as a model-call count: Demo A takes 7 calls (two plans, two for the Files agent, two for the Reader, the answer), Demo B 10 (three plans, the ceiling, plus the specialists and the answer). **Not measured:** how often the real Orchestrator obeys the new sentence. That needs the live run (the merge agent's); if it still pre-plans, the next step is a plan-time refusal (a `reader` step whose goal holds no file path is refused with a one-line reason), which costs one Sonnet call per mistake instead of two or three wasted ones, and was left out until the numbers ask for it.

**Alternatives.** Letting `delegate` carry a sharper goal ("delegate step 1: read <path>") so no re-plan is needed: the model-call count of the ideal flow is the same (a delegate is a Sonnet call like a plan is), so it would add an Action field and change the contract for no saving. Not compacting page views: they are the biggest thing in a Role's notes and every step re-reads them. Dropping the guard: it still saves the page load.

**Evidence.** `tests/test_run_efficiency.py` (3, mutation-checked: a guard that ignores shrinking, one that never fires, and one that does not mark the repeat each fail a test); `tests/test_capabilities.py` now expects the second echo's summary to read `repeat, not run again: echo hi`; `tests/test_reader_demos.py` pins the prompt sentences and the 7 and 10 call counts. Files: `src/stepout/runner.py`, `src/stepout/roles.py`.
