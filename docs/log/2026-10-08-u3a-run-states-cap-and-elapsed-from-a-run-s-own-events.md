---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: U3a: run states, cap and elapsed from a Run's own events
tags: [u3,state]
refs: [web/src/store.ts, web/src/runview.ts, web/src/testFixtures.ts, docs/plan/ui-worktree.md]
---

**What.** The state behind the run view (U3), before any view uses it. `runState` now has five finished states: `done`, `stopped` (the Runner's "Stopped by you."), `overbudget` (its "Stopped: the $1.00 budget for this run is used up."; the API calls both `stopped`, the stop event's text tells them apart), `failed` (only the API knows) and `running`. `runCap` is the budget: `cap_usd` from the `status` frame while the Run runs, from the API afterwards, `null` when unknown or zero, so no meter is ever drawn against a guess. `timeline` marks a user message `queued` (the last n of a chat that `status` says are waiting) and a reply with no Run a `note` (a decline, an unknown command, an error). `runview.ts` holds the arithmetic and wording as pure functions: spend (two decimals from a cent up, four below), elapsed time (first event to last, or to now while it runs), a step line without its URL scheme, done-of-total for the plan. `testFixtures.ts` loads `web/fixtures` as page state for tests and reads the expected totals straight from the raw JSON.

**Why.** U3 says "real numbers only". Keeping the sums in pure functions and checking them against the fixtures' own JSON makes that a test, not a promise.

**Alternatives.** Showing an indeterminate bar when the cap is unknown (an invented look of progress). Telling over-budget from stopped by the API (it does not distinguish them).

**Evidence.** `npm test`: 60 passed, including `runview.test.ts` (money, elapsed, plan progress, step lines) and the new store cases (both stop texts, failed and stopped from the API, the cap from `status` then the API, null for none). Build and lint clean.
