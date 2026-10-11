---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S6: the run card is the template's tool card (state icon, uppercase section labels, pill badges)"
tags: [ui,run-view,design]
refs: [web/src/RunBlock.tsx, web/src/Icon.tsx, web/src/App.css, docs/plan/ui-chatbot.md]
---

**What.** The run view is restyled as the template's collapsible tool card: a hairline-bordered 8 px card with no fill, a header of **state icon, summary, chevron** (the same summary text as before: `8 steps · $0.14 · 22 s`, `Stopped by you · …`, `Over budget · …`; running keeps the pulsing dot, done is a green check, stopped a ban, over budget and failed a red cross), and a body with the template's 16 px padding and uppercase 12 px section labels **Plan** and **Steps** (shown only when there is something under them). Role chips and verdicts are pill badges on `--surface-2`; step lines, costs and addresses stay monospaced; the Stop button is the template's destructive style (red text on a 10 % red wash). A Run that did not end well tints the card's **edge**, not its header, and always has its words and icon. Plan and budget meters are unchanged (real numbers against the real cap; amber from 80 %, red at the cap). Nothing in the data or the behaviour changed: the same summary text, the same lists and their accessible names, the same Stop.

**Why.** Slice S6 of `docs/plan/ui-chatbot.md`: the template's own element for "something the assistant did" is this card, so the run view reads as part of the same product.

**Evidence.** `npm test` 149 passed, including every state of the run view from the fixtures (done, running, stopped, over budget, failed, refused, queued, no run) and "a chat read back looks exactly like the chat watched live"; build, lint, `check:contrast` 118 pairs (each status colour on every surface and on its tint); Playwright 30 flows pass (run view, live view, viewer, history, motion). Screenshots: finished, running, over budget, in light and dark.
