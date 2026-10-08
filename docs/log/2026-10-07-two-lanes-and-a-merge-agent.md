---
date: 2026-10-07
kind: decision
lane: both
status: accepted
title: Two lanes in two worktrees, and a merge agent
tags: [process, worktrees, merge]
refs: [docs/plan/README.md]
---

**What.** Work runs in two parallel lanes, each in its own git worktree: **Main** and **UI** (how they start in Claude Desktop is in [the next entry](2026-10-07-lanes-as-desktop-sessions.md)). `main` is advanced only by a **merge agent** working in the primary checkout on a scratch branch: it merges both lane branches, runs the checks, and fast-forwards `main`. Files are owned by path (see the plan). Building is iterative, one capability at a time, not all up front.

**Why.** The User wants the front end to move freely, with collisions resolved in one place by one agent, and the capabilities built in iterations.

**Alternatives.** A four-lane split behind a contract-freeze phase: more coordination than one person can run now. A single branch with no lanes: UI churn would block backend merges. Making the primary checkout the Main lane: it must stay free for merging.

**Evidence.** `docs/plan/README.md`.
