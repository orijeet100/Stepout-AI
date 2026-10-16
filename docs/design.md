# Design: the rules the page follows

The page looks like ChatGPT, rebuilt in plain CSS ([ADR 0017](adr/0017-the-page-follows-the-chatgpt-look.md)); agent work is drawn as assistant-ui draws it ([ADR 0018](adr/0018-agent-work-as-assistant-ui-draws-it.md)). This file holds the rules. **Values live only in `web/src/design/tokens.css`**; components read tokens, never raw values, and the page's rules are in `web/src/App.css`. A browsable copy with a card per component is the private Design System artifact (claude.ai/artifact/4p4iVCfD1vaF4ywRqHY1Lt); if it and the repo disagree, the repo is right.

## Change a colour, size or component

1. Edit the token in `tokens.css` (every colour is `light-dark(light, dark)`), or the rule in `App.css`. No raw colours, sizes or radii in components.
2. After a colour: `cd web && npm run check:contrast` (text 4.5:1, control edges and the focus ring 3:1, light and dark).
3. Look at it in the real page, in light, dark and at 375px, not only in tests: `stepout web`, or the offline demo `python web/mock/real_backend.py`.

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

## Not taken (ADR 0017)

A model picker, attachments, voice, share, a user menu, thumbs up or down, a code-block header.

## Open

- **An accent colour.** The logo's indigo and violet appear nowhere in the interface. Indigo (`#6c75df`) is about 4:1 on white, so a text colour would need a darker shade. Decide before adding one; it changes the "no accent" rule above.
- **Row tools on a touch screen** (rename, delete in the chat list) stay 28px while every other button grows to 44px.
- **Suggestions on an empty chat** are four pills of different widths, one per row; a 2 by 2 grid of equal pills may read as more designed.
