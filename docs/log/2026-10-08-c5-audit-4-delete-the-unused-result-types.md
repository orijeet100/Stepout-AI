---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 4: delete the unused Result types
tags: [cleanup,audit,domain,adr]
refs: []
---

**What.** `FetchResult`, `AnswerResult` and the `Result` union are deleted, with their JSON round-trip test.

**Why.** Nothing in src builds or reads them: a hand returns a plain string into a Role's notes, and the page's wire types are in `contract.py`. ADR 0007 says Actions and Results are plain serializable data so hands can later run elsewhere; the Actions already prove that (`test_actions_round_trip_through_json` stays), and the only thing the Result types proved was that three unused classes serialise.

**Alternatives.** Keeping them with a note: ADR 0007 is left as written (it records the intent). When a hand really runs off the laptop, its result type arrives with its first user and its first test, shaped by what that hand returns.

**Evidence.** `git grep` finds no other reference (the glossary word 'Result' is a concept, not this class); offline suite green. Files: `src/stepout/domain.py`, `tests/test_serialization.py`.
