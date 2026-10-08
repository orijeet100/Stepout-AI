# Stepout AI — working notes

- Tests (offline, scripted model): `./.venv/Scripts/python.exe -m pytest -q`. Run: `python -m stepout.app` (terminal) or `python -m stepout.app web` (chat at http://127.0.0.1:8765; rebuild the page with `cd web && npm run build`).
- **Start with `docs/STATUS.md`** (state, decisions, what's next, gotchas). Plan of record: `docs/game-plan.md` (milestones M1–M4). Design: `docs/architecture.md`. Decisions: `docs/adr/`. Language: `CONTEXT-MAP.md`. Docs change in the same commit as behaviour.
- **Plan of record from 2026-10-07: `docs/plan/README.md`** — two lanes in two worktrees (Main B1–B6, UI U1–U6), file ownership, sync points, merge-agent procedure. In a lane? Read your lane file there first. The wire contract between the page and the backend is `docs/ui-contract.md`.
- **Log every decision and every behaviour change** in `docs/log/`, in the same commit: `python scripts/log.py new --kind change --lane <main|ui> --title "..."`. Query it with `python scripts/log.py list [--lane/--kind/--tag/--grep]`. `python scripts/log.py check --staged` must pass; enable the hook once per clone with `git config core.hooksPath .githooks`. Details: `docs/log/README.md`.
- **Adding a tool = one file in `src/stepout/capabilities/` (subclass `Capability`) plus one line in `ALL` in its `__init__.py`**, then name it in a Role's `tools` in `roles.py`. The Runner, Gate and model adapter learn it from the registry; `tests/support/echo_capability.py` is the minimal example.
- **Front door:** every message that is not a `/command` gets one cheap screening call first (`src/stepout/screening.py`): decline, plain chat, or proceed with the earlier Exchanges it links to. Its paid eval is the merge agent's: `python -X utf8 -m pytest -m eval -s tests/test_live_screening.py` (labeled prompts: `tests/data/screening_prompts.jsonl`).
- Never read or print `.env` (it holds the API key).
- File access for the agents is set by `data/config/grants.toml` (git-ignored; template `grants.example.toml`). Only the User edits it.

## Engineering skills (in `.claude/skills/`, loaded on demand — don't preload)
- Changing an interface or module boundary (Channel, Role, Action, Gate) → `api-and-interface-design`.
- Anything touching files, the web, the browser or untrusted input → `security-and-hardening`.
- Starting a milestone, or a change across several files → `incremental-implementation` (thin vertical slices, tests green at each step).
- Writing a Role's prompt or a context-heavy task → `context-engineering`.
- Using an external API or library (Anthropic, Playwright, aiohttp) → `source-driven-development`: check the official docs first.
- Orienting in a large codebase → `graphify query "<question>"` (graph in `graphify-out/`, rebuild with `graphify update .`). Not needed for small questions.

Provenance and what was left out: `docs/third-party.md`.
