# Stepout AI

A task agent you drive from your phone. Send a request on Telegram (or a React web page); it does the job with fetch/search, a browser, or by looking through folders you allow, asks you only when it's blocked, missing information, or about to do something risky, resumes after your reply, and remembers what it learned so it asks less over time. Built from scratch to learn how production agents work: permissions, state, resumption, memory, tracing, evals.

**The claim to prove:** human interventions per task fall across repeated attempts, against a memory-off control. No model training — improvement comes from recall.

**Status:** Slice 1 — domain core (Intake, Gate, Runner with fetch/search, Ledger, CLI Channel). `pytest` green offline; live CLI demo pending an `ANTHROPIC_API_KEY`. See [`docs/results/s1.md`](docs/results/s1.md).

## Docs
- [`docs/requirements.md`](docs/requirements.md) — what V0 must do, the metric, the 16-scenario acceptance script
- [`docs/architecture.md`](docs/architecture.md) — components, threat model, test layers
- [`docs/roadmap.md`](docs/roadmap.md) — slices S0–S11 and what's parked for V1
- [`CONTEXT-MAP.md`](CONTEXT-MAP.md) — the two bounded contexts and their glossaries (Assistant, Evaluation)
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`docs/brief.md`](docs/brief.md) — original brief, verbatim (partly superseded; see decision 0004)

## How we work
Trunk-based on `main`; one short branch per slice (`slice/01-agent-core`); each slice ends with a runnable demo and a result in `docs/results/`.
