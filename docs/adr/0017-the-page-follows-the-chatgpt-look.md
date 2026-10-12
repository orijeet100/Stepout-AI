# 0017 — The page follows the look of ChatGPT, rebuilt in our own CSS

Status: accepted · 2026-10-12 · supersedes [0014](0014-the-page-follows-the-vercel-chatbot-look.md)

**Decision.** The page looks like ChatGPT (chatgpt.com): one plain sheet (white, or #212121 in dark) beside a #f9f9f9 / #181818 chat list; rows in the list are rounded fills, not bordered buttons; your message is a borderless grey bubble on the right; the assistant's words sit on the page with no avatar, 16 px on 28 px lines in a 48rem column; the composer is one round pill with a round send button, and on an empty chat it sits in the middle of the screen under "What can I help with?" with the suggestions as pills beneath it; a reply has a Copy button under it; "Stepout can make mistakes" sits under the composer; on a phone the chat list slides in from the left. The "Working…" line and a running Run's summary use the shimmering text of ElevenLabs UI (ui.elevenlabs.io), redone as a CSS background sweep. Values live in `web/src/design/tokens.css`.

**No new dependency.** The page has no Tailwind, shadcn or motion library, and ElevenLabs' components are built on them, so their shapes were ported to CSS rather than installed. The stack stays Vite, React, react-markdown and plain CSS. Fonts stay the system stack (Segoe UI on Windows), which is what ChatGPT renders in there.

**Kept from 0014 and earlier:** the run card (plan, steps with verdicts and costs, meters, Stop, every end state), the live browser view and screenshot viewer, streaming, the rail that folds the list to icons, the drawer's focus rules, reduced motion, and the rules for model output (no HTML, no images, safe links).

**Deliberate differences from ChatGPT.** Status colours (green, amber, red) exist because a Run can end several ways; they pass 4.5:1 on every surface (`npm run check:contrast`). The composer's edge darkens when focused (ChatGPT's does not) so focus is visible at 3:1. Not taken: model picker, attachments, voice, share, a user menu, thumbs up/down, a code-block header.

**Why.** The User asked for the page to look as close to ChatGPT as possible. It is the chat layout most people already know, and the change is mostly tokens and one stylesheet.

**How it was checked.** 166 page tests, the 35 real-Chrome flows against the mock (four updated: no assistant tile, the drawer slides from the left, the suggestions sit under the composer, the sidebar is 260 px; the viewer flow now tabs from the run card, since the shared mock's chat list outgrew its 40 Tab presses), the contrast gate, and the built page looked at in light, dark and at phone width.
