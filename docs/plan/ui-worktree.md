# UI lane — hand-off

A Claude Desktop **worktree session** (the app names your branch) · you own `web/**` and `src/stepout/channels/web.py` · overview and rules: [`README.md`](README.md) · wire contract: [`../ui-contract.md`](../ui-contract.md) · decisions so far: [`../log/`](../log/README.md)

**You need no API key and spend nothing** until sync X2. Everything runs against a mock that replays recorded-style runs.

## Kickoff prompt (paste into the agent in this worktree)

```text
You are the UI-lane agent for Stepout AI, working in this session's worktree.
STEP 0, before anything else:
 a. Check that docs/plan/README.md and docs/ui-contract.md exist. If not, STOP and tell the User: this
    worktree was cut from a base without the plan (the plan must be pushed to main first).
 b. Make this worktree's own venv and install into it (the mock server uses aiohttp from it):
      python -m venv .venv
      .venv/Scripts/python.exe -m pip install -e ".[dev]"
 c. cd web && npm install && npm run build   (confirms the baseline builds). Report the result.
 d. Report your branch name (git branch --show-current): the merge agent needs it.
Then read, in order: CLAUDE.md, docs/STATUS.md, docs/plan/README.md, docs/plan/ui-worktree.md,
docs/ui-contract.md, docs/log/README.md, then the log entries for your lane
(python scripts/log.py list --lane ui).
You own web/** and src/stepout/channels/web.py ONLY. Never edit the Runner, Gate, Roles, Model or any other
backend file: if you need something from the backend, write it into docs/ui-contract.md plus a log entry
(kind: contract) and say so in your report. Do U1 first and stop for the User to choose a direction.
Thin slices, tests green at each step. Every decision and behaviour change gets a docs/log entry in the same
commit (python scripts/log.py new ...); update the "Lane: UI" section of docs/STATUS.md.
Commit on your branch before you report.
Model output is untrusted: render markdown without raw HTML, http(s)/mailto links only (skill: security-and-hardening).
Never read or print .env. You do not need an API key.
```

## Where the page stands (verified 2026-10-07)

`web/` is Vite 8 + React 19 + TypeScript 6 + `react-markdown` 10; `App.tsx` is 154 lines and `App.css` 97. Scripts: `dev`, `build`, `lint` (oxlint), `preview`. **There is no test runner yet.** The server replays its in-memory history on connect, so chats vanish on a restart. The wire format is in the contract (v0 today, v1 proposed).

## Setup and dev loop

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # its own venv
cd web && npm install
./.venv/Scripts/python.exe web/mock/server.py     # mock backend on :8766 (you build this in U2)
cd web && npm run dev                              # Vite on :5173, proxies /api /ws /shots to VITE_BACKEND (default :8766)
```

Point `VITE_BACKEND` at `http://127.0.0.1:8765` to try the real backend after X2.

## U1 — Design direction (S–M) · with the User

**Goal.** The User chooses a look before anything is built on it.

1. Ask the User for one or two products whose feel they want (they have not named any yet).
2. Build **three** rough directions as routes in the app (`#/design/a`, `b`, `c`), each showing the same fixture screen: a chat list, a conversation with a running run (plan checklist, steps, a cost-versus-cap meter), a finished run with screenshot thumbnails, and the open viewer. Light and dark.
3. The User picks one (or mixes). Capture it as design tokens in `web/src/design/tokens.css` (colour, type scale, spacing, radius, motion) and delete the other two.

**Done when.** The choice is a `decision` log entry with screenshots linked; tokens exist; nothing else is built yet.

## U2 — App shell on a mock, and a channel that speaks v1 (L) · needs X1

**U2a — shell and mock**
1. `web/mock/server.py` (aiohttp): serves the v1 contract from `web/fixtures/`, replays a run over `/ws` with realistic timing, and fakes `send` and `stop`.
2. `web/fixtures/`: hand-made runs in the v1 shape — a web run (plan, open, click, answer) with screenshots, a Files run with **invented** paths only, a refused action, a Stop, an over-budget stop, a Decline, and a chat reply. A small script makes the screenshots by photographing local HTML pages with Playwright (1000×700 JPEG, quality 50, like the real ones). **Never** export a real Ledger run containing the User's paths or file names.
3. The app: sidebar of chats (new chat, switch, title, preview, a running or queued dot), the message list, a composer (Enter sends, Shift+Enter is a newline), a connection banner with reconnect and back-off, empty and error states. State is React's own (`useReducer` fed by the frames); add no state library.
4. Add Vitest and React Testing Library so `npm test` exists (each new dependency gets a short log entry: why, licence).

**U2b — the real channel speaks v1** (`channels/web.py`)
1. `hello`, `message`, `trace` and `status` frames; the `/api/*` routes; the old v0 frames still accepted for one release.
2. It reads history through a small `HistoryReader` interface. Test it with a fake backed by the fixtures; at X2 it is wired to the Main lane's `history.py`.
3. The security rules of the contract, **each with a test**: `Host` check, `Origin` check and JSON content-type on `POST`, 32-hex id validation, no CORS headers.
4. Queued state: messages waiting in the inbox while a Run is active.

**Done when.** `npm run build`, `npm run lint` and `npm test` pass; the app runs from the mock end to end (send, watch, stop, switch chats); the channel's v1 tests and security tests pass; every fixture validates once the Main lane's `tests/test_contract.py` exists.

## U3 — The run view (M)

**Goal.** You see what is happening, cleanly.

1. Inline under your message: the **plan checklist** (pending, running, done, failed), then a step list with a role chip, a plain-language line (`browse open luma.com/discover`), a verdict badge (Allow, Refuse, Ask) and the step's cost.
2. **Progress bar = real numbers only:** plan steps done out of total, and a cost meter of spend against the Run's cap (`cap_usd`). Never an invented percentage.
3. Elapsed time (from event times); a **Stop** button while running; a collapsed summary once finished (`5 steps · $0.09 · 32 s`) that expands.
4. States: queued, running, done, stopped, over budget, declined, failed.

**Done when.** Component tests cover each state from fixtures; a Playwright flow (below) shows the run view updating live against the mock; the summary matches the numbers in the fixture.

## U4 — The screenshot viewer (M)

**Goal.** Click a small preview, get a big view. Simple, per the [log](../log/2026-10-07-simple-screenshot-viewer.md).

1. Thumbnails appear in the run view as `shot` events arrive.
2. Click opens a modal viewer: the large image, the page's **URL and title** (from the `shot` event), previous and next across the run, Esc or a close button, focus trapped and restored, alt text.
3. No cursor animation, no streaming. A missing image shows a clear placeholder.

**Done when.** Keyboard-only use works; component tests; one Playwright flow opens, steps through and closes the viewer.

## U5 — History and polish (M) · needs X2

1. Switch the page to the real backend: chats and runs load from `/api/*` after a restart; a past run's events load when expanded and render exactly like a live one.
2. Loading skeletons, empty states, error states, a responsive layout (a drawer under about 900 px), dark and light via `prefers-color-scheme`, reduced motion, a keyboard pass, an accessibility pass.
3. Long runs stay smooth (check with a 300-event fixture; add virtualisation only if it is measured to lag).
4. Retire the v0 frames once the User agrees.

**Done when.** The page matches the chosen direction in light and dark at three widths; the full Playwright suite passes against the mock and, at the merge, against the real backend.

## U6 — Question and approval cards (S–M) · needs X4

Cards for `question` and `approval` frames, with the exact file and destination shown, answer and approve controls, and expiry. Shapes come from the Main lane's B5 via the contract.

## UI testing

- **Components:** Vitest + React Testing Library, run by `npm test`.
- **Flows:** Playwright for Python in `web/e2e/`, run by `python -m pytest web/e2e` against the mock and a `vite preview` build: send a message and watch it run; stop; switch chats; open the viewer and step through it; reload and see history. (The Main lane's pytest config only collects `tests/`, so these do not mix with its run.) Saved screenshots stay out of git.

## Not yours

Everything outside `web/**` and `channels/web.py` · merging to `main` · anything that needs a paid call.
