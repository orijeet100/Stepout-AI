---
date: 2026-10-11
kind: change
lane: both
status: accepted
title: "The reply streams as it is written (Orchestrator's final answer, Anthropic adapter, no file read)"
tags: [streaming, ui, model]
refs: [src/stepout/model.py, src/stepout/runner.py, src/stepout/channels/cli.py, web/src/store.ts, web/src/ChatView.tsx, web/src/protocol.ts, tests/test_streaming.py, web/src/store.test.ts, docs/ui-contract.md]
---

**What.** The page showed a reply all at once when the Run ended. It now shows the Orchestrator's final answer as it is written.
- **Adapter** (`model.AnthropicModel`): `call(request, on_text=None)`. With `on_text` the request is streamed; the words of a text reply, and the growing `text` of the `answer` tool, go to `on_text` as they arrive, and the finished message is returned exactly as `create` gave it, so nothing after the call changed. The `answer` tool is sent with `eager_input_streaming: true` (without it Claude buffers a tool call's arguments and sends them whole), and its `partial_json` pieces are decoded by `_partial_text`, because the SDK's own `snapshot` leaves a string out until its closing quote has arrived.
- **Runner:** only the Orchestrator (its answer is the reply), only while the Run is not tainted, only if the model says `streams`. Words go out as `delta` trace events through the channel, never into the Ledger. A lead-in before a tool call is dropped with a `reset`.
- **Page:** `delta` frames add up in `streams` by run id and show as a reply after the Run until the finished `message` replaces them; going idle drops stragglers.
- **Terminal:** ignores `delta` (the reply arrives whole there).

**Why.** Time to first words. A three-sentence answer: first words at 2.3 s instead of 4.5 s, the same finished reply at the same time (52 frames, the streamed text equal to the finished reply).

**Why not for a tainted Run.** Its finished reply passes through `defang` (links only to addresses from the request or an earlier reply) before the User sees it. Words sent early would skip that filter, so a Run that has read a file, or builds on one, is not streamed.

**Alternatives.** A typewriter effect in the page on the finished reply: no change to what the User waits for. Having the Orchestrator answer in plain text instead of the `answer` tool (plain text streams without a flag): a prompt change that would need the acceptance set re-run.

**Evidence.** `tests/test_streaming.py` (9): the answer tool's text sent as it grows from pieces that fall anywhere, a plan's steps not sent, a text reply sent, only the answer tool asks for eager streaming, the half-escape decoder (a lone backslash, half a unicode escape, a surrogate pair), words live only and never in the Ledger, a tainted Run sends none (mutation-checked: removing the taint check fails exactly that test), a model that does not stream is called as before. Page: 5 tests (words add up and are not events, a reset, the finished reply replaces them, idle drops them, the frame parser). Live, through the running app over its WebSocket: 52 delta frames, first at 2.27 s, finished reply at 4.78 s, streamed text equal to the reply.

**Not checked.** `PydanticModel` does not stream (it has no `streams`; its replies arrive whole as before). A reply that streams and then fails (a dropped connection) leaves its words on the page until the Run's failure reply replaces them. Only the final answer streams: a Finding from a specialist does not. The plain-text answer route was not tried.
