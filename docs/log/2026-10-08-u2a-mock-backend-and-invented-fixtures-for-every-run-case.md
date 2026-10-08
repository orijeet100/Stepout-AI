---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: U2a: mock backend and invented fixtures for every run case
tags: [u2,mock,fixtures]
refs: [web/mock/server.py, web/mock/make_fixtures.py, web/mock/make_shots.py, web/mock/test_server.py, web/fixtures/, docs/ui-contract.md]
---

**What.** `web/mock/server.py` (aiohttp, port 8766) speaks the v1 contract with no model and no cost: `hello`, `message`, `trace` and `status` frames over `/ws`, and `/api/conversations`, `/api/conversations/{id}`, `/api/runs/{id}/events`, `/shots/...` over HTTP. History is built from `web/fixtures/*.json`. A `send` picks a recorded run by keyword (default: the Luma web run) and replays it under fresh ids with the recorded gaps (capped at 4 s, scaled by `--speed`); `stop` ends it at the next event with "Stopped by you."; a message sent during a run is queued and shows in `status.queued`. The mock enforces the real channel's rules (Host check, Origin and JSON content type on POST, 32-hex ids, no CORS headers) so the dev proxy is exercised against them.

Seven fixtures, each a JSON list of server frames for one chat: a web run (plan, open, click, more, answer; two screenshots), a Files run, a refused action (`refused fetch: a fetch action is not available to this role`), a Stop, an over-budget stop ($1.0028 against the $1.00 cap), a Decline, and a chat reply. Optional fields are `null`, times are ISO UTC ending in `Z`, wording copies `runner.py` and `gate.py`. Everything is invented: the only path is `D:\Example\Projects`, the pages are made-up, and the screenshots are made by `make_shots.py` photographing local HTML (installed Chrome, 1000×700, JPEG quality 50), never a real site and never a real Ledger run. `make_fixtures.py` writes the JSON so ids, parents and costs stay consistent.

**Why.** U2 needs a page that can be built and tested with no backend and no API spend, and the Main lane's contract test needs fixtures to validate (X2).

**Alternatives.** Hand-written JSON (easy to let a parent id or a cost drift). Reusing the real `WebChannel` with a fake `HistoryReader` as the mock (that is U2b, after B2; until then the mock is standalone and the rules are copied).

**Evidence.** `python -m pytest web/mock -q`: 9 passed. They check every fixture's structure (ids, `Z` times, parents appear before children, each reply's cost equals the sum of its run's events, shot files exist, no cost footer), the plan's list of cases, the history API, 404s for bad ids and traversal, Host/Origin/content-type/CORS rules, a full replay, bad `send` frames ignored, Stop, and queueing. The real contract test replaces the structural check once `src/stepout/contract.py` is merged.
