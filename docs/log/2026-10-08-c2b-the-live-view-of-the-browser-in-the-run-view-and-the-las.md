---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "C2b: the live view of the browser in the run view, and the last page when it ends"
tags: [c2,live,run-view]
refs: [web/src/Shots.tsx, web/src/RunBlock.tsx, web/src/runview.ts, web/e2e/test_live_view.py, docs/ui-contract.md]
---

**What.** In a Run's block, while the Run is running **and** the Browser agent has acted, the page shows `<img src="/live/<run_id>">` (the contract's route) in a small browser frame: a **Live** marker (hover text: "View only: nothing you do here reaches the browser"), the page's title and address from the latest `shot` event ("Opening page…" until the first one), and the stream. It is view-only by construction: while live the frame holds no button, input or link around the image, and nothing is sent back. When the Run ends the stream is dropped and the frame shows the **last saved screenshot** of the Run ("Last page"). If the stream is gone or breaks (`404`, a failed image) the frame swaps to that last screenshot the same way, and says "No page to show yet." if there is none: never a broken image. A screenshot that is missing, or whose address is not the `<run>/<n>.jpg` the backend writes, is a "Screenshot unavailable" placeholder and is never requested. A page's address is a link only if it is http(s); the model-driven title and address are text.

**Why.** Item 2 of `docs/plan/v0-finish.md` and the User's wish to see the headless browser itself. The route, its frames and the guard are already built (the channel's `LiveView`); this is the page's half.

**Alternatives.** Opening the live view only when the User clicks (the point is to watch it work). Making the live image clickable to enlarge it (a stream that is also a control invites the thought that it takes input; the saved screenshots get the viewer in the next slice).

**Evidence.** `Shots.test.tsx`: the live image and marker; the caption from the latest page; no control around it; the swap when the Run is over and when the stream breaks, with and without a saved page; nothing for a Run that never had a page or never had a Browser step; a bad run id never becomes a stream address; placeholders for missing and malformed screenshots; a non-web address as plain text. In a Run from the fixtures: live before the first page ("Opening page…"), live with its caption, the last page afterwards, none for a Files run or a chat reply, and the page a stopped Run had reached. Mutation checks: each of the live gate, the stream fallback, the placeholders, the address checks and the link check fails its test when switched off. `npm test` 86 passed. **Playwright against the mock and a production build** (`web/e2e/test_live_view.py`, 3 flows; 7 e2e in all): the live image appears, its frames are really decoded (`naturalWidth > 0`), the panel has no control, the caption follows the saved pages, the stream is gone and the last page decoded after the Run, a forced `404` shows the last page not a broken image, and a chat reply has no panel; every test fails on a console error. **Not verified:** the live stream from a real Chrome driving a real site into the page (the merge agent checked the backend chain: real headless Chrome to `live_frame` to `/live`).
