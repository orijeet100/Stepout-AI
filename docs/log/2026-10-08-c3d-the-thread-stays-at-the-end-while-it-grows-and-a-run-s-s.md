---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: C3d: the thread stays at the end while it grows, and a run's saved pages sit under its summary
tags: [ui,scroll,screenshots]
refs: []
---

**What.** (1) The thread no longer lets its last lines slide under the composer. Reproduced first, in real Chrome: with the reader at the end of a thread, a taller composer (a long multi-line message) hid the last ~95 px, and content that grew after the last event (a live frame or a page loading) hid up to ~110 px until the next event arrived. The old code scrolled only when the *number of events* changed. Now a `ResizeObserver` on the thread and on its scroll area keeps the view at the end whenever the height changes, as long as the reader is at the end (within 48 px). Rules: a message you send always goes to the end; a reply arriving does too unless you have scrolled up; scrolling up, or opening or closing a run's summary, stops the following until you reach the end again; each chat opens at its end (the view is keyed by chat). (2) A run's saved pages are a thumbnail strip *under* its card (`div.runblock`), no longer inside the summary's body, so a finished run's pages are one click or Tab away without opening it, and while it runs they appear under the live view as they are saved.

**Why.** The Merge Agent saw the last lines of an expanded run covered by the composer. Extra bottom padding would not have helped: the scroll area already ends where the composer begins, so the lines were not under it, they were below the edge of a view that had stopped following. Following the end is the cause fixed once, for every way the height can change (composer, window, images, steps).

**Alternatives.** More bottom padding (hides the symptom for one size of composer); `flex-direction: column-reverse` (pins natively but reverses keyboard and screen-reader scrolling); a "jump to latest" pill (more UI for the same rule, later if wanted).

**Evidence.** `web/src/ChatView.tsx`, `RunBlock.tsx`, `App.tsx` (key), `App.css` (`.runblock`). Vitest: thumbnails are under the closed summary, outside `<details>`, and open their page. Playwright `web/e2e/test_stay_at_end.py` (3 flows at 390 px: composer grows; a reader who scrolled up is not pulled down by a running run; opening a finished run keeps its top in view) and `test_viewer.py` (now reaches the thumbnails by Tab with the summary closed). Mutation-checked: no observer, an observer that ignores the reader, and a summary click that does not stop following each make exactly the flows that cover them fail.
