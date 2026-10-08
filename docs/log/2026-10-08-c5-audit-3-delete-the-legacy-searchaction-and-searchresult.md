---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 3: delete the legacy SearchAction and SearchResult
tags: [cleanup,audit,domain,gate]
refs: []
---

**What.** `SearchAction`, `SearchResult`, the `SearchAction` arm of `gate.check`, its place in the `Action` union and its cases in `test_gate.py` and `test_serialization.py` are deleted.

**Why.** Web search is the provider's: it runs on the API's side and never reaches us as an Action (the `web_search` capability has no Action type). Nothing built a `SearchAction`; only the Gate and two tests mentioned it, so the Gate carried a rule for an Action that cannot occur.

**Alternatives.** Keeping it as a 'future local search': that would be a capability with its own file (see CLAUDE.md), not a control Action.

**Evidence.** `git grep` finds no other reference; offline suite green. Files: `src/stepout/domain.py`, `src/stepout/gate.py`, `tests/test_gate.py`, `tests/test_serialization.py`.
