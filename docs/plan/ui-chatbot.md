# UI plan — the page looks and feels like the Vercel "Chatbot" template

Status: **plan of record for the `ui-enhancements` branch, written 2026-10-11 before any code** · lane: UI (`web/**` only) · wire contract: unchanged ([`../ui-contract.md`](../ui-contract.md)) · rules of the lane: [`ui-worktree.md`](ui-worktree.md) · log: `python scripts/log.py list --lane ui`

**Job.** The page (U1-U5, "Ink") works but is plain. Rebuild its look as the Vercel Chatbot template (github.com/vercel/chatbot, formerly "AI Chatbot"; live demo https://chatbot.ai-sdk.dev/demo, which is where chat.vercel.ai moved: `chat.vercel.ai` answers 404 today). The **look** is re-implemented in our own CSS and React (no Next.js, no AI SDK, no Tailwind, no shadcn, no new dependency). Every Stepout-specific thing stays: the streamed reply, the run view, the live browser view and screenshot viewer, history across reload, new chat, the drawer, both themes, reduced motion, keyboard use, the contrast check, and the security rules for model output.

## 1. Where the numbers come from (research, not memory)

| Source | What was read |
|---|---|
| `app/globals.css` of vercel/chatbot (main, 2026-10-11) | every colour (oklch), radius, shadow, easing and keyframe |
| `components/chat/*`, `components/ai-elements/*`, `components/ui/sidebar.tsx` | structure and every Tailwind class of shell, header, sidebar, history, messages, greeting, suggestions, composer, tool card, thinking row |
| the live demo, measured with `getComputedStyle` at 1280x800 and 375x812 | sidebar 256 px, header 56 px, column 896 px (864 px of content), composer 864x146, greeting 30 px/600, suggestion 427x55 at 13 px/500, radii 16/14/10 px, body font `ui-sans-serif, system-ui` |

Facts worth knowing before building:

- The demo **never answered** a message in about ten seconds (the guest session has no model behind it), so the **assistant side is taken from the source**, not from a screenshot. Everything on the user side was seen.
- The template loads Geist but its body actually renders in `ui-sans-serif, system-ui, sans-serif` (computed style), so our system-font stack matches what is on screen; **no font is downloaded**.
- It is **monochrome**: no accent colour. The only colour is status (green/yellow/red on tool badges). Our run-green accent goes away; the primary control is "foreground on background" (the black or white send button).
- Message text is **13 px / 1.65**, the sidebar is 13 px, labels are 10 px uppercase with 0.12em tracking. This is dense on purpose; it is what the template looks like, so we follow it.
- Some of its text is **below WCAG AA** (`muted-foreground` is 4.1:1 on the page in light; chat titles at 50 % are 2.5:1). Our contrast check is a must-keep, so those colours are nudged until they pass (section 4). That is the only deliberate visual deviation.

### Reference screenshots (in [`../log/assets/`](../log/assets/))

| | Light | Dark |
|---|---|---|
| Empty state, sidebar open | [chatbot-ref-light-empty](../log/assets/chatbot-ref-light-empty.jpg) | [chatbot-ref-dark-empty](../log/assets/chatbot-ref-dark-empty.jpg) |
| Mid conversation (your message sent) | [chatbot-ref-light-conversation](../log/assets/chatbot-ref-light-conversation.jpg) | [chatbot-ref-dark-conversation](../log/assets/chatbot-ref-dark-conversation.jpg) |
| Sidebar collapsed to its icon rail (how the demo opens) | | [chatbot-ref-dark-empty-collapsed](../log/assets/chatbot-ref-dark-empty-collapsed.jpg) |
| Phone width, empty state | | [chatbot-ref-dark-mobile-empty](../log/assets/chatbot-ref-dark-mobile-empty.jpg) |
| Phone width, chat list (a bottom sheet) | | [chatbot-ref-dark-mobile-drawer](../log/assets/chatbot-ref-dark-mobile-drawer.jpg) |
| **Ours before this work** | [chatbot-before-light-conversation](../log/assets/chatbot-before-light-conversation.jpg) | [chatbot-before-dark-conversation](../log/assets/chatbot-before-dark-conversation.jpg) |

## 2. The target look, in one paragraph

The page is the sidebar's colour. The conversation lives on a **panel inset from the top-left** (12 px rounded corner, hairline top and left edge) under a 56 px header. The **sidebar** is 16 rem: a small mark and a collapse toggle, a bordered **New chat** button, a quiet uppercase **History** label with chats grouped Today / Yesterday / Last 7 days / Last 30 days / Older, one-line rows whose open chat is full-strength with a dashed underline. The **thread** is a centred 56 rem column; **your message** is a right-aligned rounded bubble (a soft diagonal gradient, hairline edge, tiny shadow, a smaller corner at bottom-right); **the assistant** is a 28 px rounded sparkle tile with text beside it, no bubble. An empty chat shows **"What can I help with?"** centred in the panel, four **suggested actions** (2x2, one scrolling row on a phone) and the **composer**: a 16 px-radius card with a tall text area and a footer whose only strong control is a 28 px rounded send button (black in light, white in dark; grey until there is text). While it works, the assistant row shows a **shimmering** "Working…". Motion is small: messages and suggestions fade up 6-16 px on a fast spring, the greeting fades in with a delay, the composer's shadow deepens on focus, the sidebar width eases.

## 3. Template element to our component

| Template element (file) | What it is | Ours |
|---|---|---|
| `ChatShell` (`shell.tsx`) | page `bg-sidebar`; panel `md:rounded-tl-[12px] md:border-t md:border-l border-border/40` | `App.tsx` `.app` + new `.panel`; CSS only |
| `ChatHeader` | sticky 56 px, `bg-sidebar`, toggle on small screens | `App.tsx` `.head` (keeps `<h1>` with the chat title and the Running/Queued pill) |
| `AppSidebar`, `SidebarHistory`, `SidebarHistoryItem` | header mark + toggle, "New chat", group labels, 32 px rows, dashed active underline | `Sidebar.tsx`; grouping is a small pure function with a unit test |
| `SidebarRail` / `collapsible="icon"` | 3 rem icon rail | `Sidebar.tsx` + `App.tsx` (slice 7) |
| `Sheet side="bottom"` (mobile sidebar) | 70 dvh bottom sheet, top radius 16, grabber | the drawer under 900 px, restyled as a bottom sheet (slice 7) |
| `Messages`, `Greeting` | centred column; greeting centred in the panel | `ChatView.tsx` + new `Greeting.tsx` |
| `PreviewMessage` (user) | right-aligned bubble `max-w-[min(80%,56ch)]`, `rounded-2xl rounded-br-lg`, gradient secondary to muted, 13/1.65 | `ChatView.tsx` `.user` |
| `PreviewMessage` (assistant) | 28 px tile `bg-muted/60 ring-1 ring-border/50` with sparkle, text in a column beside it | `ChatView.tsx` `.turn` + `.avatar`; one tile per assistant turn (run card and reply share it) |
| `ThinkingMessage`, `Shimmer` | tile + shimmering "Waiting..." | `ChatView.tsx` `.thinking` (shown while a Run is starting and nothing has arrived) |
| `MessageResponse` (Streamdown) | markdown typography, code blocks, tables, links | `Reply.tsx` unchanged logic (react-markdown, no HTML, no images); styling in CSS |
| Scroll-to-bottom pill (`messages.tsx`) | round chip, appears when not at the end | `ChatView.tsx` (we already track "at the end") |
| `SuggestedActions` (+ `lib/constants.ts`) | 4 cards 2x2, staggered fade-up, hover lift | new `Suggestions.tsx`; four Stepout questions (web, browser, files, reader) |
| `MultimodalInput` / `PromptInput` | rounded-2xl card, min 96 px text area, footer with tools left and send right, focus shadow | `Composer.tsx` (Enter/Shift+Enter/IME behaviour unchanged) |
| `Tool`, `ToolHeader`, `ToolContent` (`ai-elements/tool.tsx`) | bordered collapsible card, header with icon, name, rounded-full status badge, chevron; uppercase 12 px section headings | `RunBlock.tsx` (the run card; plan, meters, steps and Stop all stay) |
| Not taken | model selector, attachments, visibility selector, "Deploy" button, user menu, delete chats, message actions (copy/vote/edit), artifacts, weather card, slash commands, auth | out of scope (section 7) |

## 4. Design tokens (`web/src/design/tokens.css`)

Every colour stays a `light-dark(light, dark)` hex so `npm run check:contrast` can read it; the two sets are the template's, converted from oklch (conversion script is throwaway, values below). Existing token **names are kept** so components, tests and the contrast script keep working; a few are added.

| Token | Template source | Light | Dark | Note |
|---|---|---|---|---|
| `--bg` | `--background` .985 / .195 | `#fafafa` | `#151515` | the panel |
| `--surface` | `--card` 1 / .225 | `#ffffff` | `#1c1c1c` | composer, run card |
| `--sidebar` | `--sidebar` .97 / .175 | `#f5f5f5` | `#101010` | also the page and header |
| `--surface-2` | `--secondary` .965 / .26 | `#f3f3f3` | `#242424` | bubble start, badges |
| `--fill` (new) | `--muted` .94 / .165 | `#ebebeb` | `#0e0e0e` | bubble end, code background |
| `--active` | `--sidebar-accent` (fg at 6 %) | `#e7e7e7` | `#1e1e1e` | hover and open row |
| `--text` | `--foreground` .12 / .94 | `#060606` | `#ebebeb` | |
| `--muted` | `--muted-foreground` .58 / .60 | `#636363` (nudged from `#7a7a7a`) | `#8c8c8c` (nudged from `#808080`) | **4.5:1 on every ground**; the template's value is 4.1:1 |
| `--border` | `--border` .9 / .27 at 60 % over the page | `#e9e9e9` | `#1f1f1f` | hairlines (panel edge, composer, cards) |
| `--border-strong` | (ours: the template has none) | `#838383` | `#6d6d6d` | 3:1 on every ground; the edge of a control that is not otherwise visible |
| `--ring` (new) | `--ring` .5 / .45 | `#636363` | `#717171` (nudged from `#555555`) | focus ring, 3:1 |
| `--accent` | none in the template: `--primary` is the foreground | `#060606` | `#ebebeb` | links, primary button, meter bars |
| `--on-accent` | `--primary-foreground` | `#fafafa` | `#151515` | |
| `--ok` `--warn` `--err` | tool-badge green/yellow/red (the template's are 3.3:1) | `#00782e` `#876000` `#b24039` | `#2e9e52` `#ad8522` `#dd675d` | 4.5:1 on every ground; always with an icon and words |
| radius | `--radius: .625rem` | `--r-sm` 6, `--r-md` 8, `--r-lg` 10, `--r-xl` 14, `--r-2xl` 16 px | | bubble 16/16/16/10 |
| shadow | `--shadow-card`, `-float`, `-composer`, `-composer-focus` | taken as written; dark adds the 1 px top highlight | | `light-dark()` inside each shadow |
| easing | `--ease-spring` .22,1,.36,1 · `--ease-smooth` .4,0,.2,1 | | | 150 ms hovers, 250 ms fade-up, 300 ms sidebar |
| type | system-ui; 10 / 12 / 13 / 14 / 16 / 24 / 30 px | | | message text 13/1.65; headings -0.025em |

## 5. Slices (each thin, each ends green and committed, each has its own log entry)

After every slice: `cd web && npm test && npm run build && npm run lint && npm run check:contrast`; a look at the page in the built-in browser in light and dark; `python -m pytest web/e2e -q` from slice 2 on (real Chrome; its own mock). The count of unit tests only goes up.

| # | Slice | Done when (how it is verified) |
|---|---|---|
| **S0** | This plan, the reference and "before" screenshots | committed; `log.py check` passes |
| **S1** | **Tokens and type.** `tokens.css` and the contrast script move to the template palette, radii, shadows, easing, type scale; base typography (13 px, antialiasing); no markup change | contrast script passes with the new pairs (it must list `fill`, `ring`, status colours on every ground); unit tests unchanged and green; screenshots show the old layout in the new palette |
| **S2** | **Shell, header, sidebar.** page in sidebar colour with the inset panel; 56 px header; sidebar with mark, New chat button, History label, groups by date, one-line rows, dashed active underline, running dot, queued clock | unit tests for the date grouping (Today, Yesterday, 7, 30, older, boundaries) and the sidebar (rows, selection, empty/failed/loading words); e2e `test_history`, `test_drawer` still pass; screenshot against the reference |
| **S3** | **The thread.** 56 rem column, user bubble, assistant tile with one tile per turn, 13/1.65, markdown typography (lists, code, tables, quotes, links), fade-up, the Working shimmer row, scroll-to-bottom pill | unit tests: a turn gets one tile; the shimmer row shows only while a Run is starting; the pill appears off the end and returns to it; `Reply.test.tsx` (no HTML, no images, safe links) unchanged and green; e2e `test_stay_at_end`, `test_run_view` |
| **S4** | **Empty state.** greeting, four suggested actions that send on click (disabled when offline), staggered entrance | unit tests: shown only for an empty chat that has been read, a click sends exactly that text, disabled while disconnected; screenshot against the reference; reduced motion shows them at once |
| **S5** | **Composer.** rounded card, tall text area, footer (queue note on the left while a Run is active, send on the right), focus shadow, disabled/enabled send button | `Composer.test.tsx` (Enter, Shift+Enter, IME, empty text, offline) green; e2e flows that type and send; focus ring checked at 3:1 |
| **S6** | **The run card as a "Tool" card.** header with state icon, summary, badge and chevron; uppercase section headings; meters, plan, steps, verdict badges, Stop, browser view and thumbnails restyled; every state (running, done, stopped, over budget, failed) | `RunView.test.tsx`, `States.test.tsx`, `Shots.test.tsx`, `ShotViewer.test.tsx` green; e2e `test_run_view`, `test_live_view`, `test_viewer`; one screenshot per state in light and dark |
| **S7** | **Small screens and the rail.** the drawer becomes a bottom sheet (grabber, 70 dvh, top radius 16); suggestions scroll in a row; desktop sidebar can collapse to a 3 rem icon rail; reduced motion audit | e2e `test_drawer` (updated), `test_motion` (updated); screenshots at 390 px and 900/899; keyboard: sheet traps focus, Esc closes, focus returns |
| **S8** | **Verify for real and close out.** build the page; run it from this worktree on port 8790; a streaming sampler; Stop; reload; narrow; dark; reduced motion; `STATUS.md` Lane: UI; final screenshots | the evidence list in the report (section 8) |

A change that needs a backend field would go to `ui-contract.md` as an additive change plus a `contract` log entry; none is expected, because every element above is built from data the page already has.

## 6. Risks and how they are handled

| Risk | Handling |
|---|---|
| The assistant side of the template could not be observed (the demo never replied) | built from the template's source; the report says so |
| 13 px text and soft greys are harder to read | every text colour is held to 4.5:1 by the contrast script; the type scale is tokens, so one edit changes it |
| Many e2e tests find things by class (`.chat`, `.run__sum`, `.reply`, `aside.side`, `button.menu`) | class names are kept wherever the element survives; a test is changed only when the behaviour or the DOM really changed, and the commit says which |
| The bottom sheet replaces a left drawer | same open/close/inert/focus logic; only the CSS and the e2e geometry assertions change; the breakpoint stays 900 px |
| `light-dark()` is not allowed for a whole shadow | each shadow is one declaration with `light-dark()` on its colours |
| A streamed reply must not flicker when the final message replaces it | slice 3 does not touch the store; the assistant tile and text keep their keys; checked in the sampler |
| `field-sizing: content` (composer growth) needs a recent Chrome | already used by the page today |
| The template's focus indicator is almost invisible | we keep a visible ring (`--ring`, 3:1) on keyboard focus: an accessibility requirement beats fidelity here |

## 7. Out of scope (said once)

A model picker, attachments, share/visibility, a "Deploy" button, a user menu or sign-in, deleting or renaming chats, message actions (copy, vote, edit, regenerate), artifacts and document editing, tool widgets such as the weather card, slash commands, reasoning blocks, a manual light/dark switch (the page follows the system setting, as before), a caret on the streaming text, Geist or any web font, and virtualised long lists. Nothing in the backend or the wire contract changes.

## 8. Evidence the report must contain

Branch tip commit; per-slice table; test counts (unit before 131; Playwright flows before 29; contrast pairs before 94); before/after screenshots in both themes; a live run from port 8790 with a sampler on the reply text that shows it **growing**; Stop; reload with history intact; narrow width; dark; reduced motion; spend (at most about $0.15); what still differs from the template and why; what could not be checked.
