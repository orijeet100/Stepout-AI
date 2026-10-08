---
date: 2026-10-08
kind: change
lane: docs
status: accepted
title: Consolidation: README with screenshots, STATUS brought up to date, stale Stop claims corrected
tags: [docs,consolidation]
refs: [README.md, docs/STATUS.md, docs/ui-contract.md, docs/game-plan.md, docs/assets/, docs/plan/v0-finish.md]
---

**What.** The build was frozen at the User's request and the project consolidated. (1) `README.md` rewritten: what it does, a screenshot of the live view and of a finished run in dark, light and phone widths (`docs/assets/*.jpg`, made from the final built page with real Chrome browsing a real page, the model scripted, so they cost nothing and show nothing private), how it stays safe, a quick start that was run from a fresh clone, what a task costs, how to test, and where to read next. (2) `docs/STATUS.md`: the header says what state this is (V0 consolidated, tag `sync-6`), the "Where we are" table has the rows the last two days added (chats and front door, the Reader, the page, the acceptance run), the Stop line is true. (3) The claim that Stop is "checked between steps" is corrected where it was still written (`ui-contract.md`, `game-plan.md`, a comment in `channels/web.py`): the Runner awaits the Stop flag together with every model call and hand, so a Run ends within about a second. (4) `docs/plan/v0-finish.md` says strict taint.

**Why.** The User asked to stop building and make sure everything is clean and nothing is stale. The audit of the docs for statements the work had made false found these; the rest had been corrected by the Main lane as it went.

**Alternatives.** A docs site or generated API docs: nothing here needs one. Screenshots of the real Ledger or a real run: they would carry the User's paths or files; the scripted ones do not.

**Evidence.** `scripts/log.py check --range` passes; the offline suite passes (506); the numbers in the README and STATUS come from the final live acceptance run (8 of 8, $0.27) and the live front-door eval (97%, two identical runs).
