# Stepout AI

A task agent you drive from your phone. Send a request on Telegram (or a local web page); it does the job with fetch/search or a browser, asks you only when it's blocked, missing information, or about to do something risky, resumes after your reply, and remembers what it learned so it asks less over time. Built from scratch to learn how production agents work: permissions, state, resumption, memory, tracing, evals.

**The claim to prove:** human interventions per task fall across repeated attempts, against a memory-off control. No model training — improvement comes from recall.

**Status:** Slice 0 — requirements, architecture and roadmap only; no application code yet.

## Docs
- [`docs/requirements.md`](docs/requirements.md) — what V0 must do, the metric, the 11-scenario acceptance script
- [`docs/architecture.md`](docs/architecture.md) — components, threat model, test layers
- [`docs/roadmap.md`](docs/roadmap.md) — slices S0–S9 and what's parked for V1
- [`CONTEXT-MAP.md`](CONTEXT-MAP.md) — the two bounded contexts and their glossaries (Assistant, Evaluation)
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`docs/brief.md`](docs/brief.md) — original brief, verbatim (partly superseded; see decision 0004)

## How we work
Trunk-based on `main`; one short branch per slice (`slice/01-agent-core`); each slice ends with a runnable demo and a result in `docs/results/`.
