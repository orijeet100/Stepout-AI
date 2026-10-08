---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "C3b: an honest loading state for the live view until the first page has painted"
tags: [c3,live,loading]
refs: [web/src/Shots.tsx, web/src/App.css, web/e2e/test_live_view.py]
---

**What.** The real Browser's first live frame is a blank white page, which under the old "Opening page…" caption looked like a broken image. Now, while the live stream is shown and the Browser has not yet saved any page (no `shot` event), the frame is covered by a quiet loading state, a spinner and "Opening the page…" on the neutral inset colour (`role="status"`). The stream stays connected underneath, so the live frame is ready the moment the cover lifts. The cover lifts at the first `shot` event (the page has painted and been saved) and does not come back for later pages; it is gone if the stream fails or the Run ends (then the last screenshot, or the plain words, show instead: never a spinner that does not end). The caption beside the Live marker is empty until a page is known.

**Why.** The merge agent saw it on a real Browser: a white square under a caption is indistinguishable from a broken image. A frame that is blank for a known reason should say the reason.

**Alternatives.** Hiding the live image until a `shot` event (it would then reconnect or flash on the swap; keeping the stream warm under a cover costs nothing). Detecting "blank" from the pixels (the page cannot read a stream's pixels, and a legitimately white page would be misread). Waiting for the first loaded frame (that frame *is* the blank one).

**Evidence.** `Shots.test.tsx`: the cover is over the frame with the stream still there; it lifts when the first page is saved and stays gone; it is absent once the stream has failed; in a fixture Run it shows before the first screenshot. `npm test` 105 passed. Playwright (`test_live_view.py`, now 4 flows): in real Chrome, sampled every 40 ms until the first page is saved, the live frame is never on screen without its cover while no page has been saved, the cover was really shown, and it lifted (the check fails when the cover is removed). `web/e2e` 13 flows. **Not verified:** with a real Browser on a real site (the first-frame blank is known from the merge agent's run, and the mock reproduces it with `blank.jpg`).
