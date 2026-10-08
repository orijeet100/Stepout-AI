---
date: 2026-10-08
kind: decision
lane: ui
status: accepted
title: "Colour scheme: Ink made excellent in light and in dark, designed not inverted"
tags: [design,colour,contrast,tokens]
refs: [web/src/design/tokens.css, web/src/App.css, web/scripts/check-contrast.mjs, docs/plan/v0-finish.md, docs/log/2026-10-07-look-is-direction-c-ink-graphite-mono-run-detail-run-green.md]
---

**What.** Direction C (Ink) stays the base: graphite, mono run detail, run-green. The colours are redesigned per theme, not one set flipped. **Dark:** stepped graphite (the sidebar is the deepest layer, the page above it, cards above that, an inset panel above the card), a calm green with no glow, depth from lightness alone. **Light:** a cool paper (white cards on a pale page, a deeper sidebar), a deeper green, depth from a soft shadow and firmer control edges. New tokens: `--surface-2` (an inset panel, a disabled control), `--border-strong` (a control's edge), `--accent-hover`, `--warn-soft` and `--err-soft` (tints for a header or a banner), `--shade` (the shadow colour, zero in dark). What changed on the page, found by looking at the "before" shots: an **over-budget run no longer sits on a green slab** (the meter panel is neutral and the colour lives in the bars); the **budget bar turns amber at 80% and red at 100% of the real cap**; a Run's header is tinted by how it ended (amber stopped, red over budget or failed), always with its words and icon; the **open chat has an accent edge**; the **disabled Send button is neutral**, not a faded green; the composer carries the focus alone as a 2px accent edge (it had a second ring inside it); the reconnect banner uses the amber tint.

**Why.** Item 4 of `docs/plan/v0-finish.md`: a deliberate scheme in both themes. The UI/UX Pro Max skill's guidance shaped it: keep "code dark + run green", no neon glow, never colour alone, 4.5:1 for text, visible focus.

**Alternatives.** A new accent (the User chose Ink; green is the product's "run" colour). A manual light/dark switch (the page follows the system; a switch is a U5 question). Tinting every verdict badge (more colour for no extra meaning).

**Evidence.** `npm run check:contrast` now checks 47 pairs in each theme (94 in all): text, muted text, accent, hover accent and every status colour against every surface they sit on and against their soft tints (4.5:1), and a control's edge and the focus ring against the surfaces (3:1, WCAG 1.4.11). All pass; the check was extended before the palette was changed, and it caught the dark control edge being too faint (2.96 and 2.74) before it shipped. `npm test`: 61 passed, including the 80% and 100% bar tones; lint and build clean. Same views, same data, real Chrome, 1000 by 640, reduced motion:

| View | Before, light | After, light | Before, dark | After, dark |
|---|---|---|---|---|
| A finished run, expanded | [before](assets/colour-before-light-1-finished.jpg) | [after](assets/colour-after-light-1-finished.jpg) | [before](assets/colour-before-dark-1-finished.jpg) | [after](assets/colour-after-dark-1-finished.jpg) |
| An over-budget run | [before](assets/colour-before-light-2-overbudget.jpg) | [after](assets/colour-after-light-2-overbudget.jpg) | [before](assets/colour-before-dark-2-overbudget.jpg) | [after](assets/colour-after-dark-2-overbudget.jpg) |
| A run in progress, composer focused | [before](assets/colour-before-light-3-running.jpg) | [after](assets/colour-after-light-3-running.jpg) | [before](assets/colour-before-dark-3-running.jpg) | [after](assets/colour-after-dark-3-running.jpg) |

(The sidebar list is longer in the "after" shots because each capture run adds chats to the mock.) **Not done:** the type scale and spacing are unchanged, and a pass over the screenshot viewer and live view colours belongs to C2.
