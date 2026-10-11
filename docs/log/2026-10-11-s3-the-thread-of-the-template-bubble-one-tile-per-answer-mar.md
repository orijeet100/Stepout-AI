---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S3: the thread of the template (bubble, one tile per answer, markdown, working row, way back to the end)"
tags: [ui,thread,messages,design]
refs: [web/src/ChatView.tsx, web/src/App.tsx, web/src/App.css, web/src/store.ts, web/src/Icon.tsx, web/src/Thread.test.tsx, docs/plan/ui-chatbot.md]
---

**What.** The thread is a centred 56 rem column. **Your message** is a right-aligned bubble (diagonal gradient from `--surface-2` to `--fill`, hairline edge, the template's card shadow, 16 px corners and a 10 px one at bottom right, at most 80 % or 56 characters wide) that slides in 6 px on a spring when it was just sent and not when read back from history. **Everything the assistant says in answer** (its run card, the words as they are written, the finished reply) is one row with **one 28 px sparkle tile** beside a body column; the row is keyed by the message it answers, so the streamed words becoming the finished reply do not remount the tile. A **"Working…" row** with a shimmer shows from the moment your message is taken from the queue until the first event of its run arrives (`starting()` in `store.ts`: running, this chat or not yet known, your last message, not queued); the run card then takes the same row. The reply's markdown has the template's typography (13 px at 1.65, headings, lists, links underlined, quotes, inline and block code, tables). A round **"scroll to the end"** pill appears when you have scrolled up and returns you (smooth, or at once under reduced motion). Class names the flows use (`.reply`, `.user`, `.col`, `.runblock`) are unchanged.

**Why.** Slice S3 of `docs/plan/ui-chatbot.md`: this is where the page starts to read as a chat product. The "Working…" row closes a gap the old page had: for about a second after sending there was nothing on screen.

**Not changed.** `Reply.tsx`: markdown still has no raw HTML, no images and only http(s)/mailto links with `rel="noopener noreferrer"`; its 5 tests are untouched and green. The store, the wire and the stay-at-the-end behaviour are unchanged.

**Evidence.** `npm test` 146 passed (139 before; 7 new in `Thread.test.tsx`: one tile per answer, a row per message of yours, no slide-in for history, the working row's three edges, the pill), build, lint (no warnings: the slide-in's clock is read once when the thread opens), `check:contrast` 118 pairs; Playwright 29 flows pass unchanged.
