---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "C2c: thumbnails and the screenshot viewer, keyboard-only tested"
tags: [c2,viewer,a11y]
refs: [web/src/ShotViewer.tsx, web/src/Shots.tsx, web/src/RunBlock.tsx, web/src/App.tsx, web/e2e/test_viewer.py, docs/log/2026-10-07-simple-screenshot-viewer.md]
---

**What.** A Run's saved pages (`shot` events) show in its block as **thumbnails** (title underneath, a button named "Open screenshot 2 of 3: New York · Luma"), appearing as the events arrive. Clicking one, or the "Last page" image, opens the **viewer**: a native modal `<dialog>` with the large image (alt text "Screenshot of <title>"), the page's title and address (a link only if http or https), **Previous** and **Next** across that Run's pages (they wrap; the arrow keys step too; both are disabled with one page), a counter "2 of 3" announced politely, a **Close** button, **Esc**, and a click on the backdrop. Because it is a real modal `<dialog>`, the browser makes the page behind it inert, traps focus inside, closes it on Esc, and puts focus back on whatever opened it. Focus starts on Close. A screenshot that is missing, or whose path is not the shape the backend writes, is a "Screenshot unavailable" placeholder in the strip and in the viewer, never a broken image. The strip appears only where something can open it; the live stream is never clickable.

**Why.** Item 2 of `docs/plan/v0-finish.md` and U4 of the plan: history keeps what the Browser saw. The earlier [simple screenshot viewer decision](2026-10-07-simple-screenshot-viewer.md) (thumbnails and a big view, no cursor replay) stands; the live view now sits beside it.

**Alternatives.** A focus-trap library (the native modal does it). A custom overlay `div` (everything the platform gives for free would be rebuilt: inert background, Esc, focus restore). Stopping at the ends instead of wrapping (a longer way round for a Run with many pages).

**Evidence.** `ShotViewer.test.tsx` (14 tests, jsdom with a stand-in for `showModal`): thumbnails named and indexed, appearing as shots arrive, one per page of a fixture Run, none without a viewer to open them; the viewer's content, focus on Close, Previous and Next with wrap-around, arrow keys, a single page, the three ways to close, closing when told there is nothing to show, placeholders, an untitled page. Mutation checks: with each of the arrow keys, wrapping, the backdrop click, Esc, the initial focus, the single-page lock, closing, and modality switched off, a test fails. **`web/e2e/test_viewer.py` in real Chrome with the real `<dialog>`, keyboard only:** Tab reaches a thumbnail, Enter opens, focus is on Close, the large image has decoded and has alt text, the arrows step and wrap, 16 Tab and Shift+Tab presses never put focus on page content (and the composer behind it cannot be focused), Esc closes, and focus is back on the thumbnail that opened it; and with every `/shots/` request aborted the thumbnails and the viewer show the placeholder and no `<img>` is left. `npm test` 100 passed; end-to-end 9 passed; whole offline suite 272 passed.
