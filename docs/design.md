# Design: the rules the page follows

The page looks like ChatGPT, rebuilt in plain CSS ([ADR 0017](adr/0017-the-page-follows-the-chatgpt-look.md)); agent work is drawn as assistant-ui draws it ([ADR 0018](adr/0018-agent-work-as-assistant-ui-draws-it.md)). This file holds the rules. **Values live only in `web/src/design/tokens.css`**; components read tokens, never raw values, and the page's rules are in `web/src/App.css`. A browsable copy with a card per component is the private Design System artifact (claude.ai/artifact/4p4iVCfD1vaF4ywRqHY1Lt); if it and the repo disagree, the repo is right.

## Change a colour, size or component

1. Edit the token in `tokens.css` (every colour is `light-dark(light, dark)`), or the rule in `App.css`. No raw colours, sizes or radii in components.
2. After a colour or a tint percentage: `cd web && npm run check:contrast` (text 4.5:1, control edges and the focus ring 3:1, light and dark). It also checks the blended colours `App.css` paints with `color-mix` (the Stop button's tint, a task's result, an argument chip), reading the percentages from the stylesheet. A new blended colour with text on it goes in that script's `blended` list.
3. Look at it in the real page, in light, dark and at 375px, not only in tests: `stepout web`, or the offline demo `python web/mock/real_backend.py` (scripted model, no key, no cost; `stepout-demo` in `.claude/launch.json`). A rebuilt page may need a hard reload ([`roadmap.md`](roadmap.md), design debt).
4. If the Design System artifact is kept as a copy, re-sync it after a design change.

## Content

- Plain, short, second person: "you", "your"; the product is "Stepout" or "the assistant". Say what happened, then what to do: `Could not keep that.`
- Sentence case everywhere (`New chat`, `Delete chat?`). On the page it is "run", "task", "agent", not the capitalised glossary terms.
- One `…` for anything in progress (`Working…`, `Loading chats…`). Facts in a run line are joined with ` · `: `7 actions · $0.31 · 48 s`. No exclamation marks, no emoji.
- A verb changes tense with its state: `Searching the web` while it runs, `Searched the web` after, `Not allowed to read a file` when the Gate said no.
- Money is `$0.31` from one cent up, `$0.0042` below it, and a step's cost always has four decimals. Time is `32 s`, `2 m 05 s`, `1 h 03 m`.
- A chat's title is its first message as one line, at most 60 characters, cut between words and ended with `…` (`chat_title` in `src/stepout/ledger.py`, `chatTitle` in `web/src/store.ts`: keep them identical).

## Colour

- There is no accent. The primary control is the foreground: `accent` fill with `on-accent` text (black in light, white in dark). Colour means status only: `ok`, `warn`, `err`, with `warn-soft` and `err-soft` for a banner ground.
- Status is never colour alone: pair it with an icon and a word (tick and `done`, cross and `failed`). Green and red are told apart by the icon.
- Ground, from the page outward: `bg` (the page and the conversation), `sidebar` (the list and code blocks), `surface-2` (your bubble, pills, a disabled control), `surface` (the composer and dialogs), `card` (a task card), `well` (a tool call's request and result), `track` (a bar's track and an argument chip). Text is `text`, secondary text `muted`; both hold 4.5:1 on all of them.
- A control whose only edge is a hairline needs `border-strong` (3:1) when the edge is the control: a focused composer, an input. The focus ring is `ring`, 2px, offset 2px; the composer carries focus on its own pill.
- A web page's screenshot is white and not themed (`#fff` frame, 10 by 7). Anything that stands in for a missing screenshot keeps the themed `surface-2`.

## Type, space, shape

- System fonts on purpose (`--font-body`, `--font-mono`). 14px (`fs-sm`) for the interface, 16px (`fs-md`) on 28px lines (`lh-read`) for the conversation, 13.5px (`fs-tool`) for agent work, 11px mono (`fs-2xs`) for tags, costs and arguments. Headings are 500 or 600 with `letter-spacing: -0.025em`.
- A 4px grid (`sp-1` to `sp-6`). Cards and tool panels keep the literal 14px by 10px inset and 10px row gap that assistant-ui uses.
- Text buttons, chips and pills are fully round (`999px`); the send button and dots are circles. Rows and icon buttons `r-lg`, cards, tool panels, code and dialogs `r-2xl`, your bubble `r-bubble`, the composer `r-composer`.
- Edges are hairlines (`border`, `card-edge`, `border-side`). A shadow is for what floats or lifts: the composer, the jump button, the drawer, dialogs.
- Your message is a right-aligned grey bubble; the assistant's words sit on the page with no bubble and no avatar, in a column no wider than `measure`.

## States and motion

- Hover fills `hover` in the conversation and `active` in the chat list; primary goes to `accent-hover`. Pressed: 1px down, or `scale(0.94)` on send. Disabled is `muted` on `surface-2`, neutral, never a faded fill.
- Working text shimmers; a task's bar sweeps (a tool call has no percentage); a running dot pulses. Colour changes take `--dur` (150ms); entrances use `--ease-spring`.
- Under `prefers-reduced-motion` all of it stops and shimmering words stand still in `muted`.

## Layout

- From 900px: the chat list (`sidebar-w`) beside the main column; it folds to a `rail-w` rail of icons. Under 900px it is a drawer from the left over a scrim and the page behind it is inert. Keep the `899px` in `App.css` in step with `useNarrow.ts`.
- The header is `header-h`. Under 480px the machine's name sits under the title, so the title keeps the width.
- The empty chat centres the greeting, the composer and the suggestions together on a wide screen; on a phone the composer docks at the bottom.
- Buttons and the send button are 44px under `pointer: coarse`; row tools are always visible where there is no hover.

## Icons and imagery

- One stroke set in `web/src/Icon.tsx`: 24 by 24, 2px, round caps and joins, `currentColor`, shapes from Lucide (ISC). 14px beside 13.5px text, 16px default, 12px chevrons. Add an icon there; never an emoji or an icon font.
- The mark is `web/public/icon.png` at 20px beside the name; on dark it sits on a `text`-coloured tile because its navy door vanishes on `sidebar`. Replies never show images.

## Components

One line each; the class is in `web/src/App.css`, the markup in the `.tsx` of the same name. The artifact has a card with a preview for each.

| Component | Class | The rule |
|---|---|---|
| Button | `.btn` + `--primary` `--ghost` `--danger` `--stop` `--icon` | A round pill, 36px (44 on touch). One primary per view. Danger only in a confirm dialog and never the default focus; stop only while a run works. An icon button needs `aria-label` and `title`. |
| Composer | `.dock` `.composer` `.send` | One `r-composer` pill on `surface`. Enter sends, Shift+Enter is a newline. It carries focus on its own edge (`border-strong`, `shadow-composer-focus`). Send is disabled offline or with no text. |
| Search field | `.search` | A borderless row in the chat list; fills `active` on hover and focus; its placeholder is `text` until focus. |
| Your message | `.user` | A right-aligned `surface-2` bubble, `r-bubble`, at most 70 percent or 56 characters wide; text only; a `Queued` tag while it waits. |
| Reply | `.reply` `.actions` | Markdown on `bg`, no bubble. No raw HTML, no images, links only `http`, `https` and `mailto` with `noopener noreferrer`. Copy and the cost sit under it. |
| Greeting | `.greeting` | `What can I help with?` and nothing else; centred; no subtitle, name or picture. |
| Suggestions | `.suggestions` `.suggestion` | Hairline pills in `muted`; each sends its own text; one for each hand (web, browser, files, reader); disabled offline. |
| Chat list | `.side` `.chatrow` `.chat` | Rounded fills, not bordered buttons; `active` for the open chat and on hover. Rename and delete only on an idle chat; delete asks first. A rail from 900px, a drawer under it. |
| Header | `.head` | Title on one line, the machine, a Running or Queued pill, the theme switch. No user menu, share or model picker. |
| Status | `.dot` `.pill` `.tag` | Colour plus an icon or a word. The running dot pulses. A dot on its own needs `role="img"` and a label. |
| Banner | `.banner` | On `warn-soft`, `role="status"`, with `Retry now`; one at a time. |
| Confirm dialog | `.confirm` | A native `<dialog>`. Focus starts on Cancel. Delete is `btn--danger`. Only for what cannot be brought back. |
| Progress bar | `.bar` | 3px on `track`, with `role="progressbar"` and a value text. The budget turns `warn` at 80 percent and `err` at the cap. No bar without a real limit. |
| Agent plan | `.aplan` | A title and `n of m`, a bar, a checklist. Only when the plan has more than one step. |
| Tool call | `.tool` | A quiet line that opens onto its request and result in `well`. The label's tense follows the state; a refusal reads `Not allowed to …`; the state is also text for screen readers. |
| Task card | `.task` | `card` on `card-edge`. The bar sweeps while it works and is full in `ok`, `err` or `warn` once it ends. Open while it works. |
| Run summary | `.run` | One `<details>` line: open and shimmering while running, closed facts when done. Body at most 36rem. Saved pages sit under the line. |
| Browser panel | `.browser` `.thumb` | View only. `Live` only while the run runs. A white 10 by 7 frame; a missing screenshot keeps the themed ground. |
| Screenshot viewer | `.viewer` | A native modal `<dialog>`; focus starts on Close; arrow keys step; Previous and Next are disabled with one page. |
| Memory | `.memory` | Three groups; edit and forget per entry; one input adds a Persona line. Nothing a page or file said may write here. Errors are one `err` line. |

## Not taken (ADR 0017)

A model picker, attachments, voice, share, a user menu, thumbs up or down, a code-block header.

## Open

Decisions about the look. The code-side debt (the cache header, tests, old titles) is in [`roadmap.md`](roadmap.md).

- **An accent colour.** The logo's indigo and violet appear nowhere in the interface. Indigo (`#6c75df`) is about 4:1 on white, so a text colour would need a darker shade. Decide before adding one; it changes the "no accent" rule above. (The artifact carries the logo's colours as `mark-navy`, `mark-indigo` and `mark-violet`, for its cover; `tokens.css` does not.)
- **Row tools on a touch screen** (rename, delete in the chat list) stay 28px while every other button grows to 44px.
- **Suggestions on an empty chat** are four pills of different widths, one per row; a 2 by 2 grid of equal pills may read as more designed.
- **The phone drawer has no close button.** It closes on the scrim, Esc or choosing a chat; the rail toggle that folds the list is hidden under 900px.
- **The header title and the conversation column** do not share a left edge on a wide screen: the title is at the header's edge, the column is centred at `measure`. ChatGPT does the same.
