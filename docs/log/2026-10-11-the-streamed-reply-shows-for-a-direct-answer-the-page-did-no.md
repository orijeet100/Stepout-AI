---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "The streamed reply shows for a direct answer: the page did not know its Run yet"
tags: [streaming, ui, bug]
refs: [web/src/store.ts, web/src/store.test.ts, docs/log/2026-10-11-the-reply-streams-as-it-is-written-orchestrator-s-final-answ.md]
---

**What.** The streaming entry of the same date was wrong about the page. The words arrived over the WebSocket, but the page showed nothing until the finished reply: the timeline placed a stream after its Run, and a direct answer has no event until its model call ends (the `step` is recorded then), so the page did not know the Run and dropped the stream. Fix: a stream remembers its chat (`streams[run_id] = {conversationId, text}`) and is shown at the end of that chat, which is where the reply being written belongs.

**Why it was missed.** The first check was a WebSocket client that counted frames; it never looked at the page. The second check drove the real page in a browser with a sampler on the reply's text.

**Evidence.** In the real page (built-in browser, the composer, the same heat pump question), before the fix the sampler saw the old reply, then the new one whole at 3,977 ms; after it, 35 growth steps from 14 characters at 2,103 ms to 714 at 3,962 ms, the finished reply replacing the streamed one. New page test: the words of a direct answer show although no event of its Run has arrived, and another chat does not show them (131 page tests, build and lint clean).

**Not checked.** A multi-step Run (a plan, a specialist, then the answer) in the page; the unit test covers the placement, and the browser check was a direct answer only.
