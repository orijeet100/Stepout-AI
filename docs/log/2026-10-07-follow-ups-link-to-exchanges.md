---
date: 2026-10-07
kind: decision
lane: main
status: accepted
title: A follow-up links to earlier exchanges, not just the last one
tags: [conversation, context, intake, taint]
refs: [docs/plan/main-worktree.md]
---

**What.** A Message that relates to earlier **Exchanges** in the same Conversation (not necessarily the latest) is a **Follow-up**. The front-door call returns the numbers of related Exchanges, picked from a one-line index of the last ~10. The Orchestrator receives those Exchanges in full (the request, the reply the User saw, and a one-line "what was done" such as `browsed luma.com/discover, luma.com/tech`) and **only those**. A new Task gets none. An Exchange from a Tainted Run keeps its taint, so a Run that links it is Tainted too. History does not include raw page text (it is not stored).

**Why.** It matches the User's rule: new means no history; a follow-up carries the history of what it links to. It handles "two messages about the website, one random, then the website again". It keeps hostile text in an old reply from reaching unrelated tasks.

**Alternatives.** A binary new/follow-up flag (cannot express non-adjacent links). Always attaching the last N. Storing raw page text (large, not needed yet).

**Evidence.** Planned as iteration B3; acceptance tests listed there.
