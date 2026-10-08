# Stepout AI

A task agent you drive from a chat page (Telegram later). An Orchestrator plans each request and hands steps to specialist agents, each holding one hand: web search, a headless browser, or the disk's file names. It reports back while you watch every step live, asks only when blocked, and (planned) remembers what it learned so it asks less over time. Built from scratch to learn how production agents work: permissions, state, resumption, memory, tracing, evals.

**The claim to prove:** human interventions per task fall across repeated attempts, against a memory-off control. No model training; improvement comes from recall.

**Status:** M1–M3 built and verified live (Orchestrator, Files, Browser); M4 (file contents) is next. **Start at [`docs/STATUS.md`](docs/STATUS.md)**: state, run commands, architecture diagram, every decision, what remains.

```bash
./.venv/Scripts/python.exe -m pytest -q                 # offline tests
./.venv/Scripts/python.exe -m stepout.app web           # chat at http://127.0.0.1:8765 (needs .env with ANTHROPIC_API_KEY; set STEPOUT_PORT for another port: 8765 is often taken when two checkouts run side by side)
```

## Docs
[`STATUS.md`](docs/STATUS.md) · [`requirements.md`](docs/requirements.md) · [`architecture.md`](docs/architecture.md) · [`game-plan.md`](docs/game-plan.md) · [`roadmap.md`](docs/roadmap.md) · [`adr/`](docs/adr/) · [`CONTEXT-MAP.md`](CONTEXT-MAP.md) (glossaries)

Trunk-based on `main`; thin slices, tests plus a live check each, docs in the same commit.
