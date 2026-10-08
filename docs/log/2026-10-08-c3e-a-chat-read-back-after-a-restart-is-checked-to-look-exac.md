---
date: 2026-10-08
kind: note
lane: ui
status: accepted
title: C3e: a chat read back after a restart is checked to look exactly like the chat watched live
tags: [ui,history,tests]
refs: []
---

**What.** No behaviour change: the page already rebuilt a chat from the API after a restart; this adds the checks that say it looks the same. (1) Vitest `History.test.tsx`: seven invented fixtures (web, files, refused action, stopped, over budget, a plain reply, a decline) are rendered twice, once from the live frames plus the refresh the page makes when a Run ends, once from `GET /api/conversations`, `/api/conversations/{id}` and `/api/runs/{id}/events` alone, and the markup must be identical. (2) Playwright `test_history.py`, each on the mock *and* on the real backend (scripted model, empty database, real API answers): a finished run's opened block and its answer are byte-identical before and after a reload; a run still going comes back after a reload as "Working…", open, with Stop, and keeps filling in from the wire until it ends like any other.

**Why.** The Merge Agent asked for proof that history after a restart is not a second, poorer rendering. The pass found nothing to fix, so the checks are the deliverable.

**Evidence.** `web/src/History.test.tsx`, `web/src/testFixtures.ts` (`historyOf`), `web/e2e/test_history.py`, `web/e2e/conftest.py` (`real_stack`, `real_page`; the page guard is now shared). Mutation-checked: a history that drops the saved pages makes the reload flow fail. 120 vitest, 25 end-to-end flows.
