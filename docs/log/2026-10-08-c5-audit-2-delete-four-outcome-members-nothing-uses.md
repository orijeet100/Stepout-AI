---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 2: delete four Outcome members nothing uses
tags: [cleanup,audit,domain]
refs: []
---

**What.** `Outcome` keeps `DONE`, `FAILED` and `CANCELLED`. `BLOCKED`, `DECLINED`, `EXPIRED` and `UNCERTAIN` are deleted.

**Why.** They belong to Approvals and pause/resume (S3), which do not exist: no Run ends in any of them (a decline is a reply with no Run, not an outcome), and the page's run states, `history._RUN_STATE` and the contract know only done, stopped (cancelled) and failed. An enum that lists outcomes that cannot happen invites code that handles them. The Approvals work adds what it needs, with the code that produces it.

**Alternatives.** Keeping them as a map of what is coming: the glossary (`src/stepout/CONTEXT.md`) already describes Blocker, Uncertain and the rest as concepts.

**Evidence.** `git grep` finds no use in src, tests, scripts or web/mock; the offline suite is unchanged. File: `src/stepout/domain.py` (-4 lines).
