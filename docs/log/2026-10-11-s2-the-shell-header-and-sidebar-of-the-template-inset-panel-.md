---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S2: the shell, header and sidebar of the template (inset panel, grouped history)"
tags: [ui,sidebar,shell,design]
refs: [web/src/App.tsx, web/src/Sidebar.tsx, web/src/App.css, web/src/store.ts, web/src/Icon.tsx, web/src/Sidebar.test.tsx, docs/plan/ui-chatbot.md]
---

**What.** The page is the sidebar's colour and the conversation sits on a **panel inset from the top left** (12 px rounded corner, hairline top and left edge, flush under 900 px) below a 56 px header. The **sidebar** has a mark and the "Stepout" name, a bordered **New chat** button (icon and words, same accessible name as before), and the chats **grouped Today / Yesterday / Last 7 days / Last 30 days / Older** under small uppercase labels (`chatGroups` in `store.ts`, local-time midnight as the Today edge, empty groups left out). A row is one line; the open chat is full strength with a dashed underline; the running dot and the queued clock stay on the right. The reply preview is no longer shown in the row (the template shows titles only); the full title is the row's tooltip. The connection banner moved inside the panel. Header menu button uses the panel icon. New icons: message, compose, panel, sparkles (Lucide shapes, as the rest).

**Why.** Slice S2 of `docs/plan/ui-chatbot.md`. The structure, not only the colours, is what makes it read as the template.

**Not changed.** The drawer under 900 px is still a left drawer (it becomes a bottom sheet in S7); the thread, composer and run card are restyled in S3-S6.

**Evidence.** `npm test` 139 passed (131 before: 4 for the grouping edges, 4 for the sidebar), build, lint, `check:contrast` 118 pairs; Playwright 29 flows pass unchanged (real Chrome against the mock). Screenshots in both themes against the reference in the plan.
