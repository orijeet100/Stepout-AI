---
date: 2026-10-07
kind: decision
lane: both
status: accepted
title: One run at a time across all chats
tags: [concurrency, contract, ui]
refs: [docs/ui-contract.md]
---

**What.** Runs execute strictly one at a time across all chats; a message sent while a run is active waits (the UI shows it as queued). Every event still carries a run id and a conversation id, so parallel runs can be switched on later without a contract change.

**Why.** The backend is sequential today (one cancel flag, an awaited loop). Parallel runs would need a per-run Stop, rate-limit handling and more simultaneous spend. The User: chats do not run at the same time.

**Alternatives.** True parallel runs across chats: later.

**Evidence.** `app.py` awaits each `submit`; `WebChannel.cancel` is a single flag.
