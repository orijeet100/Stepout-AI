# 0013 — The reply streams as it is written, but never for a Run that has read a file

Status: accepted · 2026-10-11

**Decision.** The Orchestrator's final answer reaches the page word by word while it is written, as `delta` trace events over the existing WebSocket (live only: never saved, never replayed; the finished reply is still the saved `message`, which replaces the words shown). A Run that has read a file, or builds on an answer that did, **is not streamed**.

**Why not for a tainted Run.** Its finished reply passes through a link filter (`links.py`) before the User sees it, so that a file cannot make the reply carry its own text out in a URL. Words sent early would skip that filter. A test fails if the check is removed.

**What it took (two things that were not obvious).**
- Claude buffers a tool call's arguments by default, and the final answer is the `answer` tool's `text`, so it arrived whole. The streaming path sends that one tool with `eager_input_streaming: true` and decodes the raw partial JSON itself, because the SDK's parsed snapshot leaves a string out until its closing quote has arrived.
- A direct answer has no `step` event until its model call ends, so the page does not know the Run yet. The first version passed a check that only counted WebSocket frames and showed nothing until the end in the real page. A stream therefore carries its chat, and the page shows it at the end of that chat. Both were found by measuring in the real browser, which is how streaming is verified.

**Scope and limits.** Only the Orchestrator's final answer; only the Anthropic adapter (the Pydantic AI adapter returns replies whole); the terminal prints the reply whole. A lead-in before a tool call is dropped with a `reset`. A connection that drops mid-reply leaves its words on the page until the failure reply replaces them. Wire detail: [`ui-contract.md`](../ui-contract.md).
