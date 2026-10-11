---
date: 2026-10-11
kind: contract
lane: both
status: accepted
title: "Trace kind delta: the next words of the reply, live only"
tags: [streaming, contract]
refs: [docs/ui-contract.md, web/src/protocol.ts, src/stepout/runner.py]
---

**What.** A new trace `kind`, `delta`, role `orchestrator`: `data.text` is the next words of the reply, or `data.reset: true` means what came so far was not the answer and is dropped. Additive (a new kind, optional fields), so `contract.py` needed no change and the page ignores it if it does not know it. Documented in the kinds table of `docs/ui-contract.md`.

**Rules.** Live only: never saved to the Ledger, never returned by `GET /api/runs/{id}/events`, never replayed after a reload (the finished reply is the saved `message`). A `message` frame for the same run replaces the words shown. Not sent for a Run that has read a file.

**Why.** Words as they are written, without a new frame type or endpoint.

**Evidence.** `tests/test_streaming.py`, `web/src/store.test.ts`, `web/src/protocol.test.ts`; see the change entry of the same date.
