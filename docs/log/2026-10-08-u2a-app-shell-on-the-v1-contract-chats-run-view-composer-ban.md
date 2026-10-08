---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: U2a: app shell on the v1 contract (chats, run view, composer, banner)
tags: [u2,shell,security]
refs: [web/src/App.tsx, web/src/useBackend.ts, web/src/Reply.tsx, web/src/Composer.tsx, web/src/Sidebar.tsx, web/src/ChatView.tsx, web/src/RunBlock.tsx, docs/ui-contract.md]
---

**What.** `App.tsx` is replaced by a shell that speaks the v1 contract only. Sidebar: your chats newest first, a New chat button, a pulsing dot on the chat that is running and a clock on a queued one. Chat: your messages, then each run (a minimal block: plan checklist, step lines with role chip, verdict and cost, and a Stop button while it runs; closed once finished), then the reply, with its cost. Composer: Enter sends, Shift+Enter is a newline, Enter during input-method composition does not send, it is disabled while disconnected, and its placeholder says a message queues while a run is active. A banner shows "Connecting…", "Disconnected. Reconnecting (attempt n)…" with Retry now, or a failed load with Retry. The socket reconnects with 1 s, 2 s, 4 s … 15 s back-off plus jitter; every (re)connect re-reads the chat list and the open chat, so frames missed while away come back from history. State is `useReducer` over the frames (no library). Styles use the Ink tokens only.

Security (docs/ui-contract.md, Security): replies render as markdown with no raw HTML, links only to `http(s)` and `mailto` with `rel="noopener noreferrer"`, and **no images at all** (an image URL in a reply is a way to send what the model has seen to someone else's server; the contract did not say this, it is added here). Every frame and API body is validated field by field before use (`protocol.ts`), unknown ones are ignored. Chat previews in the sidebar are shown as plain text (`plain()`).

**Not in this slice.** `shot` events are ignored (thumbnails are U3; the viewer, or the live browser view the User has asked for, is U4). The sidebar is hidden under 760 px (the drawer is U5). Meters, elapsed time and every run state are U3. The v0 frames are no longer understood by the page, so **until U2b the page works against the mock only**: the real backend still speaks v0.

**Why.** U2's goal is a page that can be used end to end (send, watch, stop, switch chats) before the backend has B2.

**Alternatives.** Keeping the v0 page alive beside the new one (two code paths to test for one release; the contract allows the backend to accept v0, the page does not need to). Optimistic echo of your own message (the server echoes it).

**Evidence.** `npm test`: 35 passed, three runs in a row (protocol, reducer, markdown safety, composer, back-off, and 7 app tests with a fake WebSocket and fetch: connect and load, send, a live run with Stop, queued chat, ignored frames, dropped connection with Retry, load error). Mutation checks: removing the image rule or the link filter fails its test. `npm run build` (type-checks the tests too) and `npm run lint` clean. In the browser against the mock: send and watch a run, Stop mid-run ("Stopped · 2 steps · $0.0265"), switch chats, reload (history intact), a message queued behind a run (sidebar clock, header "Queued"), kill the mock (banner and back-off, send blocked) and restart it (the page reconnects by itself, no reload).
