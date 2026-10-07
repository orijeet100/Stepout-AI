# Stepout AI — working notes

- Tests (offline, scripted model): `./.venv/Scripts/python.exe -m pytest -q`. Run: `python -m stepout.app` (terminal) or `python -m stepout.app web` (chat at http://127.0.0.1:8765; rebuild the page with `cd web && npm run build`).
- **Start with `docs/STATUS.md`** (state, decisions, what's next, gotchas). Plan of record: `docs/game-plan.md` (milestones M1–M4). Design: `docs/architecture.md`. Decisions: `docs/adr/`. Language: `CONTEXT-MAP.md`. Docs change in the same commit as behaviour.
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
