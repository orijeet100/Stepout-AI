---
date: 2026-10-11
kind: change
lane: ui
status: accepted
title: "S1: tokens and type are the Vercel Chatbot template's (neutral palette, radii, shadows, 13 px text)"
tags: [ui,tokens,contrast,design]
refs: [web/src/design/tokens.css, web/src/index.css, web/src/App.css, web/scripts/check-contrast.mjs, docs/plan/ui-chatbot.md]
---

**What.** `tokens.css` is rewritten from the template's `globals.css` (oklch converted to hex, still `light-dark()` so the page follows the system theme): a neutral palette with no accent colour (`--accent` is the foreground itself, `--on-accent` the page colour), the template's surfaces (`--bg`, `--surface`, `--sidebar`, `--surface-2`, new `--fill`, `--active`, new `--hover`), radii 6/8/10/14/16 px, the template's four shadows (the dark set adds a 1 px highlight, set in a `prefers-color-scheme` block because `light-dark()` only covers colours), a 4 px spacing grid, a type scale (10/12/13/14/16/24/30 px, message text 13 px at 1.65), and the entrance easing. Names that components use are kept; `--user-bg`, `--shade`, `--accent-soft` and `--bubble` are gone. The base page gets font smoothing, thin scrollbars and tighter heading tracking. Markup is unchanged: this slice shows the old layout in the new palette.

**Why.** Slice S1 of `docs/plan/ui-chatbot.md`: the palette and scale come first so every later slice builds on the final tokens. **Deliberate deviations:** `--muted` is `#636363` / `#8c8c8c` (the template's is 4.1:1 in light), `--ring` in dark is `#717171` (the template's is 2.5:1), status colours are chosen to reach 4.5:1 on every surface. Supersedes the look of the two Ink entries (marked `superseded`); the contrast gate and "designed per theme" carry over.

**Evidence.** `npm run check:contrast`: 118 pairs pass (was 94): text and muted on seven surfaces, accent, status on seven surfaces, soft tints, control edge and focus ring at 3:1. `npm test` 131 passed (unchanged), `npm run build`, `npm run lint` clean. The conversion and the AA search are a throwaway script (not committed); the resulting hex values are in the plan's token table.
