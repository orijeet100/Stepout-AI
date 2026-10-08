---
date: 2026-10-07
kind: decision
lane: ui
status: accepted
title: Look is direction C (Ink): graphite, mono run detail, run-green
tags: [design,u1,tokens]
refs: [web/src/design/tokens.css, web/scripts/check-contrast.mjs, docs/log/2026-10-07-u1-three-design-directions-as-a-gallery-route.md]
---

**What.** The User chose **C · Ink** after seeing three directions on the same screen. Its tokens are now `web/src/design/tokens.css` (`:root`, every colour `light-dark(light, dark)`, so the page follows the system theme). `index.css` reads them, and the old chat's `--bubble` is an alias for `--user-bg` until U2 rebuilds it. Mono type is for step lines, costs and URLs; the accent is run-green; type is the system fonts (no download). Directions A and B, the gallery route and the fixture screen were deleted; they stay in commit `c04e81c` if U3 wants the run-view markup back. `npm run check:contrast` checks every text pair in the tokens at 4.5:1 (38 pairs pass).

**Why.** The User found C "really clean". It fits a product whose main content is a log of steps, verdicts and costs.

**Alternatives.** A · Paper (warm cream, serif replies, terracotta) and B · Slate (white and graphite, teal): [A dark](assets/2026-10-07-u1-a-paper-dark.jpg), [B dark](assets/2026-10-07-u1-b-slate-dark.jpg). Self-hosted web fonts were left out: system fonts already look right on Windows 11 and cost nothing.

**Evidence.** Chosen direction, light and dark: [C light](assets/2026-10-07-u1-c-ink-light.jpg), [C dark](assets/2026-10-07-u1-c-ink-dark.jpg). These show the fixture screen as built in `c04e81c`, including the screenshot thumbnails the User has since said they do not want; only the look carries over. `npm run build` and `npm run lint` pass (one older `App.tsx` warning remains); the existing chat loads on the new tokens with no console errors.
