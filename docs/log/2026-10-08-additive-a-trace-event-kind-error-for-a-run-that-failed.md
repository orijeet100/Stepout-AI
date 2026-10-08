---
date: 2026-10-08
kind: contract
lane: main
status: accepted
title: Additive: a trace event kind error, for a Run that failed
tags: [contract, error]
refs: [docs/ui-contract.md, src/stepout/runner.py, tests/test_failures.py]
---

**What.** One new event `kind` in the trace table of `docs/ui-contract.md`: **`error`**, emitted by the Role that was acting when a model call or a hand failed, just before the Run ends `failed`. `data`: `summary` (the plain line the User is also given as the reply), `cause` (`auth`, `no_key`, `credit`, `rate_limit`, `overloaded`, `server_error`, `timeout`, `connection`, `rejected`, `malformed`, `chrome` or `internal`), `type` (the exception class, for the Ledger and a developer, not for display) and `status` (an HTTP status, when there was one).

**Why additive.** The contract already says new event kinds are free and the page must ignore unknown ones. Nothing in the page has to change; the UI lane may show the `summary` in the run view's failed state if it wants a reason there, since a failed Run's reply already says it.

**Evidence.** `tests/test_failures.py` pins the event for each cause. It is also in `GET /api/runs/{run_id}/events` replays (those are the Ledger's events, unchanged).
