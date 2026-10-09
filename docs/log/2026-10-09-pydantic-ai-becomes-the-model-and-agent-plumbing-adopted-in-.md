---
date: 2026-10-09
kind: decision
lane: main
status: accepted
title: Pydantic AI becomes the model and agent plumbing, adopted in slices, OpenRouter-ready
tags: [pydantic-ai, openrouter, model, adr]
refs: [docs/adr/0011-pydantic-ai-as-the-plumbing.md, docs/adr/0001-from-scratch.md, docs/adr/0010-one-loop-many-roles.md]
---

**What.** Pydantic AI (`pydantic-ai-slim`) becomes the layer under the model and, in later slices, the agent loop, adopted one slice at a time behind the existing seams. The Gate, the taint rule, the hands, the Ledger, the front door and the Roles' prompts stay ours. OpenRouter is the intended route to other models. Full table of slices, rules and open unknowns: [ADR 0011](../adr/0011-pydantic-ai-as-the-plumbing.md).

**Why.** The User asked to move toward model-agnostic use with OpenRouter and to make the code easier to work in: the loop's Stop, budget and retry code and the three-copy tool definitions are plumbing a library has. This is the "revisit" ADR 0001 left open; it narrows 0001 to "build what we measure" and no longer rules out a library under it.

**Alternatives.** Stay hand-built and fix four seams (taint declared on the capability, hands injected, a typed Finding, the role list generated), which stays an option for any slice that fails its check; LangGraph, Claude Agent SDK, OpenAI Agents SDK, CrewAI, smolagents, Mastra, Temporal (reasons in the ADR).

**Evidence.** The library's docs (hooks, usage limits, cancel, direct requests, OpenRouter, deferred tools, Temporal and DBOS) and a probe of the installed 2.54.0 (direct request with our tool definitions, price lookup for known and unknown models, native-tool support, exceptions). The first slice is the next entry. Slices 2 to 5 are decisions to confirm, each with its own check, not facts.
