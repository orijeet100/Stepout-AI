---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: U3b: the run view: plan, meters, elapsed, Stop, summary, every state
tags: [u3,run-view]
refs: [web/src/RunBlock.tsx, web/src/ChatView.tsx, web/src/useBackend.ts, web/src/useNow.ts, web/src/App.css, web/src/RunView.test.tsx, docs/plan/ui-worktree.md]
---

**What.** A Run under your message is one block. While it runs it is open and says `Working… · 1 of 2 steps · 17 s`; it has a **plan checklist** (pending, running, done, failed), two meters that are real numbers against real limits (**Plan** done of total, **Budget** spend against the Run's `cap_usd`, drawn only when both numbers exist, red and clamped at 100% when spend reaches the cap, with the true figure kept in the text), a **Stop** button, and a **step list** (role chip, a plain-language line such as `browse open luma.com/discover` with the full text on hover, a verdict badge Allowed / Refused / Asks you, and the step's own cost). Elapsed time is computed from the event times and ticks each second while it runs. When it ends it **collapses** to `5 steps · $0.09 · 32 s` and expands on click. Every state is visible: running; done; **Stopped by you**; **Over budget**; **Failed** (red border for the last two); a **Queued** tag on a message waiting its turn (also the header pill and the sidebar clock); and a reply with no Run (a decline, an unknown command, an error) as a note that says "No run was started", with no block and no cost. The page now re-reads a chat when its Run ends (the API then knows failed and the budget) and fetches a Run's events only when it has none, instead of every Run's events on every chat switch. Reply costs use the same money format as the summary.

**Why.** U3 of the plan, and item 1 of `docs/plan/v0-finish.md`: you see what is happening, cleanly, with real numbers only.

**Alternatives.** A percentage bar from guessed progress (invented). Putting Stop in the summary row (it is inside the open body while running, which is always open then).

**Evidence.** `npm test`: 60 passed. `RunView.test.tsx` renders every state from the invented fixtures and checks the summary against totals read from the raw fixture JSON (steps, cost, seconds) for the web run, the Files run, the stopped run, the over-budget run, a failed run, a refused action (shown as Refused), a decline (a note, no run) and a queued message; the running block is checked at a fixed clock (`Working… · 1 of 2 steps · 17 s`, meters `1 of 2 steps` and spend against the cap, Stop calls back, no meter without a cap or a plan). Build and lint clean. The Playwright flow against the mock is the next commit.
