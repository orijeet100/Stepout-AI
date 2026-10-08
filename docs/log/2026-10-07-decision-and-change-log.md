---
date: 2026-10-07
kind: decision
lane: docs
status: accepted
title: Every decision and behaviour change gets a log entry
tags: [process, docs, log]
refs: [docs/log/README.md, scripts/log.py]
---

**What.** Every decision and every behaviour-changing commit gets a markdown entry in `docs/log/` (frontmatter: date, kind, lane, status, title, tags, refs). `scripts/log.py` creates, lists and filters entries, and checks that code changes carry one. A pre-commit hook (opt-in per clone) and the merge agent's range check both fail a code change that has no entry. History before 2026-10-07 lives in `docs/adr/` and `git log`.

**Why.** The User wants everything recorded and queryable, so "how did we do that?" can be answered later. One file per entry means no merge conflicts between lanes.

**Alternatives.** One growing CHANGELOG file: conflicts across lanes, and not filterable. Commit messages only: not structured.

**Evidence.** `tests/test_log.py`.
