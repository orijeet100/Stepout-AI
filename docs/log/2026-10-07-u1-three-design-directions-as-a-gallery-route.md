---
date: 2026-10-07
kind: change
lane: ui
status: accepted
title: U1: three design directions as a gallery route
tags: [design,u1,gallery]
refs: [web/src/design/, web/src/Root.tsx, web/src/main.tsx, docs/plan/ui-worktree.md]
---

**What.** `#/design/a`, `#/design/b`, `#/design/c` show the same invented fixture screen in three directions: a chat list; a finished run (plan checklist, steps with role chip, verdict badge and cost, screenshot thumbnails, the reply); a running run (plan 1 of 3, budget `$0.0739 of $1.00`, elapsed, Stop); the composer; and the screenshot viewer (a native `<dialog>`). `?theme=light|dark` forces a theme (default follows the system), `?viewer=N` opens the viewer. Anything else in the hash is the chat, unchanged. A is **Paper** (warm cream, serif replies, terracotta; closest to Claude.ai), B is **Slate** (white and graphite, one sans, teal; closest to ChatGPT), C is **Ink** (cool graphite, mono run detail, run-green).

**Why.** U1 asks the User to choose a look before anything is built on it. The three directions differ only in design tokens (`directions.css`, each token once as `light-dark(light, dark)`); the components read tokens only. So choosing one is mechanical: its block becomes `web/src/design/tokens.css` and the rest is deleted.

**Alternatives.** Three separate component trees (more code, and the comparison would then be about markup, not look). A router library for three hash routes (a `useSyncExternalStore` hook is enough). Self-hosted web fonts now (the previews use system font stacks; the chosen direction's fonts are added after the pick, with their own dependency entry).

**Evidence.** Files: `web/src/design/{directions.css,fixture.css,gallery.css,fixture.ts,FixtureScreen.tsx,DesignGallery.tsx,Icon.tsx,useHash.ts}`, `web/src/Root.tsx`, `web/src/main.tsx`. `npm run build` and `npm run lint` pass (one older `App.tsx` lint warning remains). Contrast: every text/background pair in all three directions, light and dark, is at least 4.5:1 (checked with a throwaway script). Checked in the browser pane at 1280 and 375 wide: no console errors, no horizontal overflow; the viewer steps with the arrow keys, closes on Esc and returns focus to the thumbnail. No test runner exists yet (Vitest arrives in U2).
