---
date: 2026-10-07
kind: decision
lane: both
status: accepted
title: When writes arrive, every write asks for an Approval
tags: [approvals, safety, egress]
refs: [docs/adr/0010-one-loop-many-roles.md]
---

**What.** Write capabilities (upload, submit) will need an Approval card showing the exact file and destination, every time. Auto-approve for approved sites and full autonomy are parked until Evaluation exists. ADR 0010's read-only rule stands until Approvals ship (iteration B5), then it is amended.

**Why.** The User's call: ask for everything for now. Uploads move data off the laptop (Egress).

**Alternatives.** Auto-approve for approved sites; full autonomy: both later.

**Evidence.** None yet; this is policy.
