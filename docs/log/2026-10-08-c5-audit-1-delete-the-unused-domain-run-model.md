---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 1: delete the unused domain.Run model
tags: [cleanup,audit,domain]
refs: []
---

**What.** `domain.Run` is deleted: a Pydantic model of 'one attempt at a Task' that nothing ever built. A Run is a database row (`runs`) and, while it executes, `runner._Run`.

**Why.** The merge agent's ponytail audit of the whole tree (verified by grep: no reference in src, tests, scripts or web/mock). A second description of what a Run is, that is not the one in use, is how the next reader gets it wrong.

**Alternatives.** Keeping it for the Approvals work: it would not fit (pause/resume checkpoints a Role stack, not these four fields) and git remembers it.

**Evidence.** `git grep` finds no other reference; the offline suite is unchanged. File: `src/stepout/domain.py` (-9 lines).
