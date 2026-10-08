---
date: 2026-10-07
kind: decision
lane: main
status: accepted
title: Unlisted paths belong to Main
tags: [worktrees, ownership]
refs: [docs/plan/README.md, scripts/owners.py]
---

**What.** The ownership table in `docs/plan/README.md` names the UI lane's paths (`web/**`, `channels/web.py`, its hand-off file), the shared ones (`docs/ui-contract.md`, `docs/log/*`, `docs/STATUS.md`) and Main's code paths. It does not say who owns the rest: `CLAUDE.md`, `README.md`, `CONTEXT-MAP.md`, `.gitignore`, `grants.example.toml`, `.env.example`, `docs/architecture.md`, `docs/adr/`, `docs/requirements.md`, `docs/game-plan.md`, `docs/roadmap.md`, `docs/third-party.md`. In `scripts/owners.py` these belong to **Main**, so a UI-lane branch that touches one is flagged.

**Why.** The UI lane is the narrow, well-bounded one; project-wide files describe the backend and the process. Flagging beats silently allowing: a stray file swept up by a "push" shows up at the merge instead of after it.

**Alternatives.** Treat unlisted paths as shared (both lanes may edit): no false alarms, but no catch for strays. Fail both lanes on them: forces the table to name every file, so every new doc needs a rule.

**Evidence.** `RULES` and `DEFAULT` in `scripts/owners.py`; `tests/test_owners.py`. Reversible: to give the UI lane a file, add a rule and a log entry. `docs/STATUS.md` is shared because its two lane sections cannot be told apart by path; each lane edits only its own section.
