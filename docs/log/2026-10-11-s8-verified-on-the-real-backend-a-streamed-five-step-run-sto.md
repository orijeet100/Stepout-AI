---
date: 2026-10-11
kind: note
lane: ui
status: accepted
title: "S8: verified on the real backend: a streamed five-step run, Stop, a direct answer, reload, a phone, reduced motion"
tags: [ui,verification,streaming,e2e]
refs: [docs/plan/ui-chatbot.md, web/e2e/test_streaming.py, web/e2e/test_motion.py, web/src/App.css]
---

**What was run.** The real app from this worktree (`STEPOUT_PORT=8790 python -m stepout.app web`, built page, the primary checkout's key, no grants file), driven in the built-in browser and in real Chrome. A `MutationObserver` on the page recorded the reply text's length, the number of assistant rows and tiles, and whether the "Working…" row was up.

| Check | Result |
|---|---|
| A multi-step run: "What's the news in New York today?" (clicked as a suggested question) | plan, `web_search`, a repeat skipped, answer, the Orchestrator's reply: **5 steps · $0.02 · 11 s** (the reply's own cost, which includes the front door, $0.04) |
| The reply **streams** | the sampler saw **43 distinct lengths from 12 to about 560 characters over 2.1 s**, in **one row with one tile** (never two rows, never the words and the finished reply both on screen); the "Working…" row was up before the first word. The length is not strictly increasing: it dips by 2 to 22 characters five times, where a half-written markdown link or bold completes and its syntax disappears |
| A direct answer: "What is 2 + 3? Explain in two sentences." | 1 step · $0.0047; **9 distinct lengths from 5 to 98 over about 4.6 s**; one new row (2 to 3), not 4 |
| Stop: "What's the weather in Boston today?" pressed Stop at 3 steps | card "Stopped by you · 3 steps · $0.0073 · 6 s", reply "Stopped by you." |
| Reload | all three exchanges back with their run summaries and costs |
| New chat; chat list as a bottom sheet at 375 px; dark | greeting and suggestions as in the template's phone view; the sheet opens over a blurred scrim and New chat closes it |
| Reduced motion (computed styles in real Chrome, on the real app) | greeting, suggestions, composer, send button, sidebar: no animation, transitions 0 s. **It found one miss:** the app's own grid-column transition (the rail) was still 0.3 s, because the rule covered `.app *` but not `.app`. Fixed, and `test_motion.py` now reads `.app` and the empty state's entrances (mutation-checked: without the fix the flow fails) |

**Spend.** About **$0.08** of the $0.15 allowed (the three replies' costs, which include the front door: $0.04 + $0.03 + $0.0065). Everything else ran on the mock.

**Suites at the end.** `npm test` 151 passed, `npm run build`, `npm run lint` (no warnings), `npm run check:contrast` 118 pairs, `python -m pytest web/mock -q` 13 passed, `python -m pytest web/e2e -q` 35 passed. Console clean in every captured session.

**Not checked.** A real phone or tablet; Firefox and Safari; a streamed reply for a Run that had read a file (the backend sends no `delta` for it, by contract); the live headless-browser view on a real site (the merge agent's check, as before: the mock feeds it).
