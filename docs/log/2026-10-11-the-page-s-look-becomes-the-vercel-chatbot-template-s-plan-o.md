---
date: 2026-10-11
kind: decision
lane: ui
status: accepted
title: The page's look becomes the Vercel Chatbot template's; plan of record is docs/plan/ui-chatbot.md
tags: [ui,design,plan,tokens]
refs: [docs/plan/ui-chatbot.md, web/src/design/tokens.css, docs/log/2026-10-07-look-is-direction-c-ink-graphite-mono-run-detail-run-green.md, docs/log/2026-10-08-colour-scheme-ink-made-excellent-in-light-and-in-dark-design.md]
---

**What.** The page is rebuilt to look and feel like the Vercel "Chatbot" template (github.com/vercel/chatbot, demo https://chatbot.ai-sdk.dev/demo): page in the sidebar's colour with an inset rounded panel, a sidebar with grouped history, a centred message column with a right-aligned bubble for you and a sparkle tile for the assistant, a greeting with four suggested actions, a rounded composer with a 28 px send button, and the run view as a template-style collapsible tool card. The look is **re-implemented in our own CSS and React** (no Next.js, no AI SDK, no Tailwind, no shadcn, no new dependency). Tokens come from the template's `globals.css`, converted from oklch to hex so `check:contrast` can still read them. Every Stepout-specific feature stays (streamed reply, run view, live view, viewer, history, drawer, both themes, reduced motion, keyboard, contrast, model-output safety). The plan, the element-to-component mapping, the slices and the risks are in `docs/plan/ui-chatbot.md`.

**Why.** The User's brief: the page is ugly and should look and feel like the template. This supersedes the **look** of two earlier entries (Ink: graphite with a run-green accent; the colour scheme built on it). What survives from them: colours designed per theme and not inverted, status never shown by colour alone, and the contrast check as a gate.

**Alternatives.** Keep Ink and only restyle components (rejected: the brief is "exactly like" the template). Adopt Tailwind and shadcn/ui so the template's classes can be copied (rejected: a build-chain and dependency change for what plain CSS tokens do; the lane rule is to avoid new dependencies). Use the Geist font (rejected: the template loads it but its pages render in the system font, as measured on the live demo, so the system stack is already identical).

**Deliberate deviations (said here once).** Text colours the template sets below WCAG AA (muted text 4.1:1 in light, history titles 2.5:1) are nudged until they pass 4.5:1, and the focus ring stays visible. The assistant side could not be observed on the demo (it never replied during the research), so it is built from the template's source.

**Evidence.** Research notes and numbers: `docs/plan/ui-chatbot.md` section 1. Reference screenshots (light and dark, empty, mid-conversation, collapsed rail, phone, phone sheet) and "before" screenshots are in `docs/log/assets/chatbot-ref-*.jpg` and `chatbot-before-*.jpg`. No code changed in this commit.
