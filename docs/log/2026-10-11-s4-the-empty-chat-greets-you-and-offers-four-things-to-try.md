---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S4: the empty chat greets you and offers four things to try"
tags: [ui,empty-state,design]
refs: [web/src/Greeting.tsx, web/src/Suggestions.tsx, web/src/Composer.tsx, web/src/ChatView.tsx, web/src/App.tsx, web/src/App.css, web/e2e/test_empty_state.py, docs/plan/ui-chatbot.md]
---

**What.** An empty chat (a new chat, or one that has been read and has no messages) shows **"What can I help with?"** centred in the panel with a quieter line under it (our own words: it plans the steps, shows each one, tells you the cost), and four **suggested questions** above the composer: one for each hand (the news, the Luma events, a count of files by type, the newest PDF). They are a 2 by 2 grid from 640 px and one scrolling row below; each rises in on a spring one after another and lifts 2 px on hover. A click sends exactly that text, as if typed. They are disabled while the connection is down, and absent while a chat is being read, when it failed to load, and once it has a message. The greeting fades in with the template's delays; reduced motion shows everything at once. The composer's placeholder is "Ask anything…" (with "(queued while a run is active)" while a run is). Also fixed: a component's own colour lost to the page's `button { color: inherit }`; that rule now has zero specificity.

**Why.** Slice S4 of `docs/plan/ui-chatbot.md`. The old empty state was one muted sentence.

**Evidence.** `npm test` 149 passed (146 before: composer offers none unless asked, four and a click sends that text, disabled offline; the empty chat offers them and a chat with messages or one still loading does not), build, lint, `check:contrast` 118 pairs; Playwright 30 flows pass (29 before + `test_empty_state.py`: greeting, four cards in a grid above the composer, a click sends that text and they go away). Screenshots in both themes against the reference.

**Open.** The four suggestions name folders (Documents, Downloads) the User may not have granted; the Files hand then says so, as for any such question.
