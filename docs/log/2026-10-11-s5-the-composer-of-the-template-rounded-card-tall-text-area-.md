---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S5: the composer of the template (rounded card, tall text area, round send button)"
tags: [ui,composer,design]
refs: [web/src/Composer.tsx, web/src/App.css, web/e2e/test_empty_state.py, docs/plan/ui-chatbot.md]
---

**What.** The composer is the template's prompt card: 16 px radius, hairline edge, the template's soft shadow (deeper on focus, eased over 300 ms), a text area at least 96 px tall that grows to 192 px (13 px at 1.625), and a footer whose only control is a **28 px rounded send button**: foreground on background when there is text (85 % on hover, 95 % scale on press), a quiet grey disc when there is none or the connection is down (44 px on touch screens). The page's four suggestions and the card sit in one "dock" centred at the thread's width. Clicking anywhere on the card puts the cursor in the text area. Enter sends, Shift+Enter is a newline and Enter during input-method composition does nothing (unchanged, and still tested).

**Why.** Slice S5 of `docs/plan/ui-chatbot.md`. **Deliberate deviation:** the template's focus state is a 6 % shadow, which is not a visible focus indicator; the card keeps the template's shadow and also takes the 3:1 `--ring` colour as its edge while the text area has focus (the contrast check pairs `ring` with every surface it can sit on).

**Evidence.** `npm test` 149 passed (the composer's six behaviour tests are unchanged), build, lint, `check:contrast` 118 pairs; Playwright 30 flows pass (the empty-state flow measures layout positions, not painted ones, because the cards are rising in while it looks).
