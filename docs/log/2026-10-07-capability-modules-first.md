---
date: 2026-10-07
kind: decision
lane: main
status: accepted
title: Refactor to capability modules before adding capabilities
tags: [modularity, capabilities, refactor]
refs: [docs/plan/main-worktree.md]
---

**What.** The first Main iteration (B1) makes every tool a **capability module**: tool schema, action type, executor, Gate rule and a one-line blurb in one place; Roles reference capabilities by name. No behaviour change: the existing offline tests and the live smoke suite are the safety net. Goal: a new capability is **one new file plus one registration line**.

**Why.** Adding the Browser capability meant editing `domain.py`, `model.py` (tool schema and action parser), `gate.py`, `runner.py` and `roles.py`. The Reader, uploads and file writes are coming, and each would pay that cost again.

**Alternatives.** Add capabilities straight into the five files: faster now, slower every time. A plugin system with dynamic loading: a scope trap named in the roadmap.

**Evidence.** The five-file edit was read from the code on 2026-10-07.
