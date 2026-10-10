# 0011 — Pydantic AI is the plumbing; the Gate, the hands and the Ledger stay ours

Status: accepted · 2026-10-09 · Refines [0001](0001-from-scratch.md) (its "revisit if a library solves something in an afternoon") and the Model seam of [0010](0010-one-loop-many-roles.md)

**Decision.** Pydantic AI (`pydantic-ai-slim`) becomes the layer under the model and, in later slices, under the agent loop. It is adopted **one slice at a time, behind the seams that already exist, with the offline tests green after each**, so V0's frozen behaviour never depends on an unproven step. OpenRouter is the intended route to other models: a Role's model is a logical tier (`strong`, `cheap`), and what runs behind each tier is configuration.

| Slice | What moves | Status |
|---|---|---|
| 1 | The Model port gets a second adapter on `pydantic_ai.direct.model_request`; tiers are re-pointed by `STEPOUT_STRONG_MODEL` / `STEPOUT_CHEAP_MODEL` | done |
| 2 | `web_search` becomes an ordinary capability that goes through the Gate like every other; a small `Searcher` hand makes one provider search per call (it was a server-side tool inside the model call, and skipped the Gate) | done |
| 3 | Each capability's tool becomes one typed function (schema, validation and Action from the signature; today three copies per tool) | next |
| 4 | The loop: one Pydantic AI `Agent` per Role, the Gate as a hook, `AgentRun.cancel()` for Stop, `UsageLimits(cost_limit)` for the $1 cap, a typed `Finding` for hand-offs | |
| 5 | Pause/resume and Approvals (B5) with deferred tool calls and our SQLite | |

**Stays ours, whatever the library does:** the Gate's rules and the taint rule, the hands and their own limits (Fetcher, Browser, Files, Reader, redaction), the Ledger and Trace, the front door, the web channel, every Role's prompt. These are the parts the project measures and defends ([0001](0001-from-scratch.md)); the library replaces plumbing under them.

**Why.** The User wants other models (OpenRouter first) without a rewrite, and less repeated code: each tool is written three times and the loop carries Stop, budget and retry code a library already has. Its docs and installed code show the pieces we need (one request without a loop; a veto hook that can tell the model why; per-run cancel; a dollar limit; test models; OpenRouter routing with a data policy). Not run yet for slices 2 to 5.

**Rejected.** LangGraph (a graph runtime for durable, branching workflows: the right tool for pause/resume later, heavy for a single-user read-only app); Claude Agent SDK (a harness that gives an agent a computer, Anthropic only: opposite to one narrow hand per Role); OpenAI Agents SDK (Claude only through LiteLLM; its hand-off moves control, ours keeps it with the Orchestrator); CrewAI, smolagents (writes code, which the Gate cannot classify), Mastra (TypeScript). **Temporal** is not used now: it adds a server and a worker to a one-process app, stores every prompt and tool result in its history, and still needs our own at-most-once guard; revisit it in V1 when the brain moves to a server (ADR 0007), where its workers fit hands that connect outward. Pause/resume (slice 5) needs only deferred tool calls plus our SQLite; DBOS is the next step up if replay of finished steps is wanted in one process.

**Rules that keep every option open.** What a run shares (`Deps`) holds ids and settings, not live objects; tools are `async`; no secret travels in `Deps`; a tool result stays small and capped; an unknown price fails the Run instead of reading as free.

**Costs and open unknowns.** A dependency that moved from 1.x to 2.x within a year and releases several times a week (pinned `>=2.54,<3`). To prove before slice 4: that `web_search` can be closed after a file read once it is a client tool (a native tool is not seen by `prepare_tools`); that a specialist's step cap can coexist with a shared `usage`; what full message history costs against our compact notes; that Trace and Ledger rows map cleanly from its hooks. OpenRouter adds a third party between us and the model: route with `require_parameters` and a data policy that denies collection, and pin providers for acceptance runs so a silent fallback does not change what is measured.
