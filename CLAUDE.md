# Stepout AI: working notes

- Tests (offline, scripted model): `./.venv/Scripts/python.exe -m pytest -q`. Run: `python -m stepout.app` (terminal) or `python -m stepout.app web` (chat at http://127.0.0.1:8765; rebuild the page with `cd web && npm run build`). After a `git pull` that changes `pyproject.toml`, run `pip install -e ".[dev]"` again.
- **Orient with `docs/architecture.md`** (the map), then `docs/history.md` (what was decided and built), `docs/adr/` (the decisions), `docs/roadmap.md` (what is next, known debt). The wire between the page and the backend is `docs/ui-contract.md`; the vocabulary is `CONTEXT-MAP.md`. Docs change in the same commit as behaviour.
- **Decisions:** one that is hard to reverse, surprising or a real trade-off gets an ADR in `docs/adr/` (short, dated, never rewritten into a different story: amend or supersede). Small changes are `git log`.
- **Adding a tool = one file in `src/stepout/capabilities/` (subclass `Capability`; its tool schema comes from the Action class via `tool_from`) plus one line in `ALL` in its `__init__.py`**, then name it in a Role's `tools` in `roles.py`. The Runner, Gate and model adapters learn it from the registry; `tests/support/echo_capability.py` is the minimal example. **If the tool can reach the network, set `reaches_web = True` on it**: the Gate then closes it for any Run that has read a file's contents.
- **Front door:** every message that is not a `/command` gets one cheap screening call first (`src/stepout/screening.py`, [ADR 0012](docs/adr/0012-the-front-door.md)). Its paid eval: `python -X utf8 -m pytest -m eval -s tests/test_live_screening.py` (labelled prompts: `tests/data/screening_prompts.jsonl`).
- **Models:** Claude by default; `STEPOUT_STRONG_MODEL` and `STEPOUT_CHEAP_MODEL` re-point the two tiers through Pydantic AI ([ADR 0011](docs/adr/0011-pydantic-ai-as-the-plumbing.md)).
- **Verify UI features in the real page**, not only over the WebSocket: the first streaming check passed on frames and failed in the browser ([ADR 0013](docs/adr/0013-the-reply-streams.md)).
- Never read or print `.env` (it holds the API keys).
- File access for the agents is set by `data/config/grants.toml` (git-ignored; template `grants.example.toml`). Only the User edits it.

## Engineering skills (in `.claude/skills/`, loaded on demand: don't preload)
- Changing an interface or module boundary (Channel, Role, Action, Gate) → `api-and-interface-design`.
- Anything touching files, the web, the browser or untrusted input → `security-and-hardening`.
- A change across several files → `incremental-implementation` (thin vertical slices, tests green at each step).
- Writing a Role's prompt or a context-heavy task → `context-engineering`.
- Using an external API or library (Anthropic, Playwright, aiohttp, Pydantic AI) → `source-driven-development`: check the official docs first.
- Orienting in a large codebase → `graphify query "<question>"` (graph in `graphify-out/`, rebuild with `graphify update .`). Not needed for small questions.

Provenance and what was left out: `docs/third-party.md`.
