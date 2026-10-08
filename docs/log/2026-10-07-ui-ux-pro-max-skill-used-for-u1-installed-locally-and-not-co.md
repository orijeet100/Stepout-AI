---
date: 2026-10-07
kind: note
lane: ui
status: accepted
title: UI/UX Pro Max skill used for U1, installed locally and not committed
tags: [design,skill,u1]
refs: [docs/plan/ui-worktree.md]
---

**What.** The User asked for the UI/UX Pro Max skill (`nextlevelbuilder/ui-ux-pro-max-skill`, MIT) for the UI lane. It was not installed, so it was installed with `npx uipro-cli@2.2.3 init --ai claude` into `.claude/skills/ui-ux-pro-max/`. That folder is **not committed**: it is hidden through `.git/info/exclude`, and `.claude/` is outside the UI lane's paths. To use it on another machine, run the same command.

**Why.** It holds a searchable table of styles, palettes, font pairings and UX rules, which seeded the three U1 directions (Nature Distilled, Minimal Swiss, Dark Mode OLED / "code dark + run green") and the pre-delivery checklist (contrast, focus states, reduced motion, 44 px touch targets, no emoji icons, consistent icon set).

**Alternatives.** The already-installed `frontend-design` skill (no style or palette data). Committing the skill (a third-party tree outside our paths; it would also need a `docs/third-party.md` entry).

**Evidence.** Its scripts only read local CSVs; `--persist` is the only thing that writes, and it was not used. Limit found: its `--design-system` generator recommends landing-page patterns (hero, CTA), which do not fit a chat app, so only its style, colour, typography and UX data were used and layout came from the plan.
