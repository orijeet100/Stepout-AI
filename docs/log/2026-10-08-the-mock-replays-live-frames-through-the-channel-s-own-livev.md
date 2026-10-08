---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "The mock replays live frames through the channel's own LiveView"
tags: [live,mock]
refs: [web/mock/server.py, web/mock/make_shots.py, web/fixtures/blank.jpg, web/mock/test_server.py, web/vite.config.ts]
---

**What.** `web/mock/server.py` now has `GET /live/{run_id}`, served by the channel's own `LiveView` class (imported from `stepout.channels.web`), so the page is built and checked against the real streaming code, with no backend and no Chrome. While a replayed Run has a Browser step the mock feeds the view about four frames a second (the real Browser's ceiling): a blank page first (`web/fixtures/blank.jpg`, made by `make_shots.py` the way the screenshots are), then the fixture screenshot of the page the replayed Browser has "opened" (each `shot` event switches the image). The view's streams end when the replayed Run ends or Stop is pressed. `vite.config.ts` proxies `/live` like `/api`, `/shots` and `/ws`.

**Why.** Task 2 of cycle C1: the live `<img>` in the page is C2's (U4), and it needs something to point at before the Main lane's `on_frame` exists.

**Alternatives.** A second, simpler stream implementation in the mock (two copies to keep in step, and the mock would not test the real one). Looping the same screenshot only (no blank-then-page change to watch).

**Evidence.** `python -m pytest web/mock -q`: 12 passed, stable over three runs. The new tests replay the Luma web run and read `/live/{run_id}` with a multipart reader: every part is a JPEG that is either the blank page or one of the fixture screenshots, the page changes while watching, the stream ends by itself with the Run, then 404; a bad id and an unknown Run are 404 and a foreign Host is 403; and a Run with no Browser step opens a stream that simply ends with the Run. The whole offline suite is 256 passed, the end-to-end flows 4 passed, vitest 60 passed. **Not verified:** the page rendering the stream (C2).
