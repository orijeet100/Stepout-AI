---
date: 2026-10-09
kind: change
lane: main
status: accepted
title: Slice 1: PydanticModel, a second Model adapter, re-points the strong and cheap tiers to any provider
tags: [pydantic-ai, openrouter, model]
refs: [src/stepout/pydantic_model.py, src/stepout/model.py, src/stepout/app.py, scripts/acceptance.py, tests/test_pydantic_model.py, pyproject.toml, .env.example, docs/adr/0011-pydantic-ai-as-the-plumbing.md]
---

**What.** The first slice of [ADR 0011](../adr/0011-pydantic-ai-as-the-plumbing.md): a second implementation of the existing `Model` port, built on `pydantic_ai.direct.model_request` (one request, one response, no agent loop). The Runner, Gate, Roles and every other test are untouched.
- **`PydanticModel`** (`pydantic_model.py`): offers the same tools (`model.client_tools`: control tools, capability tools, one-off tools such as `screen`) as function tools, with `reaches_web` in each tool's `metadata`; offers `web_search` as Pydantic AI's `WebSearchTool(max_uses=remaining)` when the provider supports it (otherwise the agent gets its other tools and a warning is logged); asks for one tool call per turn (`parallel_tool_calls=False`: the Runner runs one, a second used to be dropped silently); sends `temperature` only when set. A reply becomes an Action through `model.call_to_action`, the parser both adapters now share. Failures become `Failure`s with a plain line and a cause (`no_key`, `auth`, `credit`, `rate_limit`, `server_error`, `rejected`, `malformed`, `connection`), as in the Anthropic adapter.
- **Price.** On the default route (a Role's own Anthropic model) it uses the same `PRICING` table, so the two adapters agree to the cent. On any other route it uses the published price of the model that answered; **a model with no known price fails the Run (`pricing`) instead of reading as free**, because a free reading would let the $1 cap never trip.
- **Config.** `STEPOUT_STRONG_MODEL` (Orchestrator, Browser agent) and `STEPOUT_CHEAP_MODEL` (front door, Direct, Files, Reader) hold a Pydantic AI model string such as `openrouter:openai/gpt-5.2`. With neither set the app runs exactly as before on `AnthropicModel`. `app.default_model` is the one place that chooses, so the app and `scripts/acceptance.py` agree; the start-up check asks only for the keys the chosen models need (`OPENROUTER_API_KEY` and so on).
- Dependency: `pydantic-ai-slim[anthropic,openai]>=2.54,<3` (`pyproject.toml`, `docs/third-party.md`).

**Why.** The User wants to run other models, first through OpenRouter. The Model port already isolates the provider, so a second adapter is the smallest change that delivers it, and it can be compared with the Anthropic adapter on the same eight acceptance queries before anything else moves.

**Alternatives.** An OpenAI-compatible adapter written by hand (about the same size, and we would own every provider's quirks); changing the loop first (a larger step with more unknowns, taken after this one proves the provider layer).

**Evidence.** `tests/test_pydantic_model.py` (33): the same cases as `tests/test_model.py` (tools offered, search capped and dropped, every tool call to its Action, text-only answer, a tool not offered, sources of citations not applicable), plus one tool call per turn, temperature, JSON-string arguments, `reaches_web` metadata, price on the default and another route, an unknown price failing closed, eight provider failures to plain lines, no key, config from the environment and the start-up check. The whole offline suite passes. Files: `src/stepout/{pydantic_model,model,app}.py`, `scripts/acceptance.py`, `tests/test_{pydantic_model,acceptance}.py`, `pyproject.toml`, `.env.example`.

**Not checked.** No live call through this adapter yet (it needs the User's OpenRouter key and a spending say-so). Not yet known: that the live acceptance queries give the same answers and a similar cost through it on Anthropic and on OpenRouter; that `parallel_tool_calls=False` is accepted by every provider; the cost figures OpenRouter itself reports; and the source links of a web search (the Anthropic adapter appends the cited pages, this one does not; slice 2 makes search a client-side tool whose links we control).
