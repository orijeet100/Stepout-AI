---
date: 2026-10-07
kind: change
lane: ui
status: accepted
title: U2a: page protocol parser and state reducer
tags: [u2,state,protocol]
refs: [web/src/protocol.ts, web/src/store.ts, web/vite.config.ts]
---

**What.** `protocol.ts` types the v1 wire format (docs/ui-contract.md) and checks every frame and API body field by field before the page trusts it; unknown frame types and fields are ignored, as the contract requires. `store.ts` is one reducer fed by frames and API responses, plus selectors: chats newest first with `running`/`queued`/`idle` from the status frame, a run's state, and a chat's reading order (your message, its run, then the reply; a message queued behind a busy run sorts after the earlier reply, not before it). The cost footer shim is here: until sync X2 the page strips `\n\n(cost: $…)` from assistant text and reads the cost from it, in one function (`splitCostFooter`) to delete later. `vite.config.ts` proxies `/api`, `/shots`, `/ws` to `VITE_BACKEND` (default the mock on 8766) and presents the target's own origin, because the backend answers only its own Host and Origin.

**Why.** Frames carry model output, so they are untrusted. One reducer keeps live frames and history loaded over HTTP in the same shape (contract rule 3). Folding frames is pure logic that can break silently, so it is unit tested.

**Alternatives.** A state library or zod (no new dependency for a few checks). Optimistic local echo of your own message (the server echoes it as a `message` frame; echoing twice would need de-duplication by content).

**Evidence.** `npm test`: 16 tests across `protocol.test.ts` and `store.test.ts`, including malformed and unknown frames, replayed frames changing nothing, out-of-order events, and the queued-message reading order. Mutation check: removing the reply-follows-its-run rule makes the queued-message test fail.
