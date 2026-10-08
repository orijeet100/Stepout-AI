---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "Run view: '1 of 1 step', not '1 of 1 steps'"
tags: [u3,wording]
refs: [web/src/RunBlock.tsx, web/src/RunView.test.tsx]
---

**What.** The Plan meter and the running summary say "1 of 1 step" for a one-step plan (and "1 of 2 steps" otherwise). Found by looking at an over-budget Run in the browser, which showed "0 of 1 steps".

**Why.** A visible wording bug in the run view.

**Alternatives.** None worth the words.

**Evidence.** `RunView.test.tsx` asserts `1 of 1 step` for the Files run (a one-step plan); `npm test` 60 passed.
