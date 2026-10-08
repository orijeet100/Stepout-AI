---
date: 2026-10-07
kind: decision
lane: both
status: accepted
title: The lanes run as Claude Desktop worktree sessions; the plan must be pushed first
tags: [process, worktrees, desktop]
refs: [docs/plan/README.md]
---

**What.** Each lane is a Claude Desktop session started with the **worktree** option; the app creates the worktree under `.claude/worktrees/` and names the branch (`<branch prefix>/<name>`, prefix `claude` by default). The primary checkout `D:\Stepout AI` stays on `main` and is where a plain merge session works. Because a new worktree starts from `origin/main` on the remote (the app default, `worktree.baseRef: "fresh"`), the plan is committed and pushed to `main` **before** the lanes start, and each kickoff prompt begins with a Step 0 that checks for it, builds the lane's own venv, runs the baseline and reports the branch name. No `.worktreeinclude`: the lanes get no `.env`. `.claude/worktrees/` is git-ignored. The merge agent builds the merge on a scratch `integrate` branch and asks before pushing `main`.

**Why.** It is the mechanism the User is using; it is verified against the official docs (worktrees and desktop pages) rather than assumed. Keeping `.env` out of the lanes follows least privilege: they only run offline tests.

**Alternatives.** `git worktree add` by hand with fixed branch names (works, but fights the app's session and cleanup model). `worktree.baseRef: "head"` so local commits suffice (not verified for the desktop app; pushing is simpler and is also a backup). Using the primary checkout as the Main lane (it would no longer be free for the merge agent).

**Evidence.** Official docs: code.claude.com/docs/en/worktrees and /desktop (2026-10-07).
