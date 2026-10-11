---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "The mock streams the reply as delta frames, and a flow proves the words grow in one row"
tags: [ui,mock,streaming,e2e]
refs: [web/mock/server.py, web/mock/test_server.py, web/e2e/test_streaming.py, docs/ui-contract.md]
---

**What.** `web/mock/server.py` now sends a Run's reply as `delta` traces (three words every 0.15 s before `--speed`) just before the finished `message`, exactly as `docs/ui-contract.md` describes: live only (broadcast, never stored, never in `GET /api/runs/{id}/events`), `role: orchestrator`, `data: {text}`, cost 0. A new Playwright flow (`web/e2e/test_streaming.py`) puts a `MutationObserver` on the page, sends a question, and checks that the reply text **grows** over at least four distinct lengths, only ever grows, starts well before the end, is never on screen twice, and that there is **one assistant row and one tile throughout** (so the finished reply replaces the words without the row being rebuilt). A mock test checks the frames themselves.

**Why.** The page's streamed reply was only checkable against a paid model. With the look rebuilt around a single assistant row, the offline mock needs to stream too, so the behaviour is proven for free on every run. No contract change: the mock follows the contract that exists.

**Evidence.** `python -m pytest web/mock -q` 13 passed (+1); Playwright 33 flows (+1). On the dev page the sampler read the reply at 12, 31, 45, 64, 81 ... 288 characters over 16 steps, with at most one tile and one row. (The two mock files are CRLF in the index and stay CRLF.)
