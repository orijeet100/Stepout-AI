---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S7: the chat list is a bottom sheet on a phone and folds to a rail on a desktop"
tags: [ui,drawer,sidebar,responsive]
refs: [web/src/App.tsx, web/src/Sidebar.tsx, web/src/App.css, web/src/design/tokens.css, web/e2e/test_drawer.py, web/e2e/test_rail.py, docs/plan/ui-chatbot.md]
---

**What.** (1) **Under 900 px** the chat list is a **bottom sheet** like the template's (70 % of the screen high, 16 px top corners, a grabber, a blurred scrim, a spring slide), replacing the left drawer. Everything that made the drawer safe is unchanged: the page behind is `inert`, focus moves to **New chat** and returns to the menu button, Esc, the scrim or choosing a chat closes it, closed it cannot be tabbed into, and a skip link leads to the message box. The boundary is still 899/900 px. (2) **From 900 px** a **Collapse sidebar** button in the sidebar folds the chat list to a 3 rem rail of two icons (expand, new chat), as the template's `collapsible="icon"` does; the history leaves the tab order while folded; the choice is kept in this browser (`localStorage`, wrapped in try/catch: without storage it still works for the visit). The column eases over 300 ms and not at all under reduced motion.

**Why.** Slice S7 of `docs/plan/ui-chatbot.md`: the template's phone layout and its first impression (it opens as a rail). The bottom sheet was the one structural change that broke e2e geometry (the scrim test clicked a point the sheet now covers: it clicks above the sheet).

**Evidence.** `npm test` 151 passed (+2: the rail toggle's names and tooltip, the App's fold/unfold and persistence), build, lint, `check:contrast` 118 pairs; Playwright 32 flows pass (+1 `test_rail.py`: 256 to 48 px and back, survives a reload, New chat works from the rail; +1 in `test_drawer.py`: the sheet is full width, sits on the bottom edge, is about 70 % high and has the 40 px grabber). Screenshots at 390 px (sheet open, empty chat) and the rail at 1280 px.
