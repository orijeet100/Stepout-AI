---
date: 2026-10-08
kind: decision
lane: both
status: accepted
title: A live headless-browser view replaces the screenshot-only viewer
tags: [ui,browser,live]
refs: [docs/log/2026-10-07-simple-screenshot-viewer.md, docs/log/2026-10-08-live-view-get-live-run-id-and-the-browser-on-frame-seam.md, docs/plan/v0-finish.md]
---

**What.** While a Run's Browser agent works, the run view shows the headless browser's page live (view-only: the User cannot click or type in it). The thumbnails and the big viewer for the Run's saved screenshots stay, for history and for stepping back through a finished Run. This supersedes the part of [the simple screenshot viewer](2026-10-07-simple-screenshot-viewer.md) that said "no live screencast"; its thumbnails, caption (URL and title) and previous/next stay as decided there.

**Why.** The User asked for it twice: the UI lane's STATUS recorded "the User wants the browser view to be the live headless browser, not screenshots" and waited for a yes before U4, and the User's instruction of 2026-10-08 was to "see the headless browser and all that happening". Seeing the page paint and change is what makes the assistant's work legible, and it is the clearest answer to "what is it doing with my browser?".

**Alternatives.** Screenshots only (what was built): cheap and honest, but static between steps. Interactive take-over of the headless browser: it opens a path for the User's clicks into the assistant's session and for pixel clicks the Gate cannot judge (ADR 0010); out of V0. A video recording: the User would watch after the fact, not during.

**Consequences.** One additive contract change ([the contract entry](2026-10-08-live-view-get-live-run-id-and-the-browser-on-frame-seam.md)); `browser.py` gains a frame callback (Main lane); the channel gains a streaming route and the page an `<img>` (UI lane). The Gate and the read-only rule are untouched: the stream only shows what the Assistant's own headless browser already rendered.

**Evidence.** Decided by the merge agent under the User's delegation of 2026-10-08. Built and measured in the V0 finish plan ([`../plan/v0-finish.md`](../plan/v0-finish.md)), cycles 1 and 2.
