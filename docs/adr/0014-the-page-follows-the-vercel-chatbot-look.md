# 0014 — The page follows the look of the Vercel Chatbot template, rebuilt in our own code

Status: accepted · 2026-10-11 · supersedes the first look ("Ink") of 2026-10-07/08

**Decision.** The page's look and structure follow Vercel's open-source Chatbot template (github.com/vercel/chatbot): the page in the sidebar's colour with an inset rounded panel, a 56 px header, a sidebar with a bordered New chat button and history grouped by age, a centred message column, a greeting with four suggested questions, a rounded composer, the assistant's work as a collapsible tool card. The values (colours in light and dark, radii, type scale, spacing, motion) were measured from the template's source and its live demo and written as our own tokens (`web/src/design/tokens.css`). **No template code was copied**: the stack stays Vite, React and plain CSS, with no Next.js, no Vercel AI SDK and no new dependency.

**Kept from Stepout, because the template has no equivalent:** the run card (plan checklist, steps with their verdicts and costs, spend against the cap, elapsed time, Stop, every state), the live headless-browser view and screenshot viewer, streaming, history that survives a restart, the drawer under 900 px (now a bottom sheet), reduced motion, and the rules for model output (no HTML, no images, safe links only).

**Deliberate differences.** Muted text, the focus ring and status colours are slightly stronger, because the template's values fail WCAG AA (muted text is 4.1:1 in light) and the contrast check (118 pairs) is a must-keep. Not taken: model picker, attachments, share or visibility, a Deploy button, a user menu, delete, message actions, artifacts. No code-block header, copy button or syntax colours (react-markdown with our CSS), and no streaming caret.

**Why.** The first look worked but was plain. A known, well-tested chat layout is a better starting point than inventing one, and rebuilding it in our own CSS keeps the page small and ours.

**How it was checked.** 151 page tests, the real-Chrome flows against the mock and against the real backend, the contrast gate, and the real app in a browser (streaming measured, Stop, reload, a phone width). Not checked: a real phone, Firefox or Safari.
