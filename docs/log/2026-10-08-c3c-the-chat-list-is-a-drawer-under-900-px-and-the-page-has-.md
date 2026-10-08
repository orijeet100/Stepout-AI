---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: C3c: the chat list is a drawer under 900 px, and the page has a skip link
tags: [ui,a11y,responsive]
refs: []
---

**What.** Under 900 px the chat list is no longer a column that takes the screen; it is a drawer opened by a menu button in the header (`aria-label="Chats"`, `aria-expanded`, `aria-controls="chats"`). Open, it acts like a modal: the page behind it is `inert`, focus moves to its first button, Esc or a tap on the scrim closes it, choosing a chat or "New chat" closes it, and focus goes back to the menu button. Closed, it is `inert` and `visibility: hidden`, so Tab can never land in it. At 900 px and up nothing changes: the list is simply there and the menu button is hidden. A "Skip to the message box" link is the first stop in tab order (visually hidden until focused) and leads to the message box (`id="message"`), past the whole chat list.

**Why.** On a phone the 260 px list left no room for the chat. A drawer that is only reachable when it is visible, and that traps focus when it is open, is what a keyboard or screen-reader user needs from it too. The skip link is the cheap fix for "Tab through 40 chats before you can type".

**Alternatives.** A bottom sheet (worse with the on-screen keyboard); a `<dialog>` for the drawer (the list must stay in the page at wide widths, and `<dialog>` cannot switch between "modal" and "just there" by media query); a JS focus trap (the `inert` attribute on everything outside does the same job with no code to keep correct).

**Evidence.** `web/src/useNarrow.ts` (matchMedia `(max-width: 899px)`), `App.tsx`, `Sidebar.tsx`, `Composer.tsx`, `Icon.tsx`, `App.css`. Vitest: drawer opens/closes, Esc, scrim, choosing a chat, `inert` on both sides. Playwright `web/e2e/test_drawer.py` (5 flows, real Chrome): open/choose/scrim/new chat then a working chat at 390 px; the 899/900 boundary; Tab never reaches the closed drawer, focus stays inside the open one in both directions, Esc restores focus to the menu button; the skip link is first in DOM order and lands on `#message`; no horizontal overflow and nothing painted past the right edge at 390 px with a whole browser run expanded.
