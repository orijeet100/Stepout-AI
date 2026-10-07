# 0001 — Build what we measure; borrow plumbing

Date: 2026-10-06 · Status: accepted (refined from "build everything from scratch")

**Decision.** Hand-write the parts we measure and defend: the router, agent loop, memory, gate, and run manager. Borrow plumbing: Playwright (browser control), the Anthropic SDK (model calls), Pydantic, pytest, and aiogram (Telegram transport, MIT). No agent framework and no record/replay tool is wrapped.

**Why.** The goal is to learn how production agents work; wrapping the core hides exactly those parts. The Telegram transport teaches little and has edge cases a library already handles.

**Prior art surveyed 2026-10-06 (reference reading only):** browser-use/workflow-use (AGPL-3.0, self-described early), Stagehand's action cache (MIT), Skyvern's code caching (AGPL-3.0), Playwright Test Agents, mem0 / Letta / Zep / Anthropic's memory tool for memory.

**Consequences.** More code to write and test; full understanding of every layer; no AGPL obligations. Revisit if a slice stalls on something a library solves in an afternoon.
