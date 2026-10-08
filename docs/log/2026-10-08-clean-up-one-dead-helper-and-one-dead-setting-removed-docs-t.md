---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Clean-up: one dead helper and one dead setting removed, docs the Reader made stale brought up to date
tags: [cleanup, docs]
refs: [docs/plan/v0-finish.md, src/stepout/ledger.py, .env.example, docs/STATUS.md, README.md]
---

**What.** The Main lane's share of done-when item 8 (nothing stale, nothing dead).
- **Dead code.** A scan of every name defined in `src/stepout` against `src`, `tests`, `scripts` and `web/mock` found one name used nowhere: `Ledger.cost_since` (written in the first slice for a monthly cap that was never built; no test, no caller). Removed. `STEPOUT_MONTHLY_CAP_USD=25` in `.env.example` is the same story (nothing reads it, so it promised a cap that does not exist): removed. If a monthly cap is built (S6) it is a new feature with a test, not a leftover.
- **Everything compiles with warnings as errors** (`python -W error -m compileall src tests scripts web/mock`).
- **Stale text corrected, because the Reader landed:** README status line, `docs/game-plan.md` progress, `docs/roadmap.md` current focus, STATUS ("Next: M4", the Remaining list, the two Open questions the Reader answered (patterns, pypdf is BSD-3-Clause), the known gap "history lives in memory until restart", which B2 fixed), the glossary's Exchange entry (it can be Tainted), and a "Since" line on the strict-taint entry that said C3 would build what C3 built. Two honest ceilings added to the known gaps: a timed-out PDF read leaves its worker thread running, and the 10 MB limit is one total per Run.

**Not done here (the merge agent's, with the whole tree).** The header of STATUS (date, sync line), the architecture diagram's wording, the ADR index, the `superseded` marks across `docs/log`, the web lane's sections, and the lint and build of `web/`. There is no linter or type checker in the project's dev dependencies; adding one is a choice for the User, so none was installed.

**Alternatives.** Keeping `cost_since` for later: the log and git history keep it, and nothing leaves a trace of a feature that is not built better than a function nobody calls.

**Evidence.** The scan (a short throwaway script, not committed), `compileall` clean, offline suite green (see the C3 entry in STATUS for the count). Files: `src/stepout/ledger.py`, `.env.example`, `README.md`, `docs/`.
