---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "New chat is instant: a draft, so typing at once cannot land in the old chat"
tags: [bug,chats,race]
refs: [web/src/store.ts, web/src/useBackend.ts, web/src/App.test.tsx, web/src/store.test.ts]
---

**What.** "New chat" now only selects a *draft* (`draft: true`, nothing selected): the header reads "New chat" and the empty state shows at once. The chat is made when its first message is sent (`POST /api/conversations`, then the `send` frame to that id), as it already was when no chat was open. A chat-list reload (a reconnect, a Run ending) no longer replaces a draft with the first chat.

**Why.** Found by the Playwright flow for the live view. "New chat" used to start a `POST` and select the new chat only when it came back; a message typed in that gap was sent to the chat that was still selected, and then the page switched to the new, empty chat, so a Run happened out of sight. A fast typist (or a script) could hit it. A side effect worth keeping: the page no longer creates an empty chat on the backend for every click.

**Alternatives.** Disabling the composer until the chat exists (a visible wait for nothing). Selecting the new chat's id optimistically before the backend answers (an id the backend did not make).

**Evidence.** `App.test.tsx`: click New chat, type and press Enter at once, and the `send` frame goes to the new chat's id and nothing to the old one (this fails with the old behaviour). `store.test.ts`: a draft survives a chat-list reload, and choosing a chat or making one ends it (each also fails when its line is removed). `npm test` 86 passed, three runs.
