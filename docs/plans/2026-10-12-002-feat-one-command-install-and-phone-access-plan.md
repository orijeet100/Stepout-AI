---
title: "feat: One-command install and phone access"
type: feat
status: done
date: 2026-10-12
origin: conversation 2026-10-12 (install friction; phone to laptop over Tailscale)
---

# feat: One-command install and phone access

Status: done. U10 (the optional Folders panel) and `stepout init --provider` were left out. The first `stepout remote` run on a real tailnet with a phone is still to do.

## Overview

A stranger on Windows finds the repo and, with as little as possible, ends up chatting with their own laptop from their phone:

1. Install one tool (`uv`), run **one command**.
2. Paste an API key, say yes to a folder. The chat opens.
3. `stepout remote`: sign in to Tailscale on laptop and phone, scan a QR code.

Two milestones, each ends with a check on a clean machine:

- **M1, one command** (U1 to U5): install, first run, no Node, no venv, no hand-edited files.
- **M2, phone** (U6 to U8): reach the laptop from a phone, safely.

No new capability, no model change, no change to the Gate, Taint or the read-only rules.

## Problem Frame

Today the README asks for about ten things. From the code, what actually blocks a clean install:

| Blocker | Where |
|---|---|
| The page is built by `npm` and `web/dist` is git-ignored, so Node is required | README, `.gitignore` |
| The page is found at `parents[3] / "web" / "dist"`: an installed package would not find it | `channels/web.py:36` |
| Data and config are `Path("data/...")`, relative to wherever it is run; `.env` is read from there too | `app.py:35-40`, `load_dotenv()` |
| The "Assistant's own folder" block is computed from the source tree, so it would not cover a per-user data folder | `files.py:28` |
| No console script; only `python -m stepout.app [web]` | `pyproject.toml` |
| `mem0ai` is a required dependency but is only imported when `OPENAI_API_KEY` is set | `memory.py:build`, `pyproject.toml` |
| `.env` and `grants.toml` are copied and edited by hand | README |
| Only `channel="chrome"` is tried | `browser.py:104` |
| Host/Origin guard accepts localhost only | `channels/web.py:254` |

## Requirements

Install
- **R1** One documented command installs and starts the app on a Windows machine that has only `uv` and Chrome or Edge.
- **R2** First run asks only for the API key and which folders to allow. Nothing is edited by hand.
- **R3** Data lives in one per-user folder, never the working directory or the package. A source checkout keeps `./data`, so development is unchanged.
- **R4** That folder is blocked from the file hands, like `.env` and `.ssh` (security).
- **R5** Upgrading the tool keeps chats, Memory and settings.
- **R6** Off Windows the file hands fail closed (the block list is Windows paths).

Phone
- **R7** `stepout remote` takes a user with nothing to a scannable QR code. Each step prints only the next action and waits.
- **R8** Only our exact host name and the owner's Tailscale login get through the guard. Tailscale Funnel (public internet) is never used.
- **R9** The page shows which laptop it is talking to, and can be added to the phone's home screen.
- **R10** The laptop does not idle-sleep while Stepout runs.

Quality
- **R11** The offline suite is green at every unit. Each milestone is verified by an install into a clean environment and, for the page, in the real browser.

## Scope Boundaries

Not in this plan:

- A `.exe` installer, Docker, auto-update, PyPI publication (see Open questions).
- A hosted hub, a login page of our own, multi-user, Telegram, a queue for a sleeping laptop.
- Phone-side Approvals or any write capability. Remote is read-only like local.
- macOS or Linux file hands. The app may start there; Files stay off (R6).
- A `doctor` command: the start-up notes already say what is missing and the fix.

## Key Decisions

1. **One tool, `uv`.** It fetches Python 3.12 and makes its own environment, so the user installs no Python, no venv, no Node. Already used on this machine (`docs/third-party.md`).
2. **The page is built in CI and shipped inside the wheel, not committed.** The repo stays clean. Install points at the Release's wheel.
3. **Home folder resolution:** `STEPOUT_HOME` if set, else `./data` when run from a source checkout (a `pyproject.toml` named stepout beside `src/`), else the per-user app folder (`%LOCALAPPDATA%\Stepout`). One function; every `Path("data/...")` derives from it.
4. **`stepout init` is a terminal act by the User.** The page and the model never write `grants.toml`. This keeps "only the User edits it" true, and a remote session cannot widen the Grants.
5. **Tailscale Serve, not Funnel, not our own hub.** Free, no domain, no server code, reachable only by the owner's devices. The guard adds exact host names and checks the owner's login header as a second layer, because a tailnet can hold more than one person.
6. **The server still binds `127.0.0.1`.** Tailscale connects locally. We never bind `0.0.0.0`.
7. **Grants change only from the laptop itself, by the User, in the terminal.** Not from the chat, the model, a phone or a remote page. A browser cannot hand a server a real folder path (only names and handles), so a page picker would mean browsing the disk through the server for whoever has the page. A local-only "Folders" panel is the optional U10: the **laptop** opens the Windows folder dialog (the browser cannot give a real path), only for a request that did not arrive under a remote host.

## Units

### U1. One home folder
**Goal:** every path the app uses comes from one place; the new folder is blocked from the agents.
**Files:** new `src/stepout/paths.py`; `app.py`, `files.py`, `memory.py`, `channels/web.py` (defaults); tests.
**Approach:**
- `home()` per Key Decision 3; `app.py` constants (`DB_PATH`, `GRANTS_PATH`, `SHOTS_PATH`, `LOGS_PATH`, `MEMORY_PATH`, `CAPTURE_PATH`) become `home() / ...`.
- `.env` is loaded from `home()` first, then the current folder (dev).
- `files.py` adds `home()` to the blocked prefixes next to the source-tree folder.
- Start-up notes name the real paths.
**Verification:** tests for the resolution order; `blocked_reason(home()/anything)` is blocked; the whole existing suite passes unchanged (dev keeps `./data`).

### U2. Ship the page and a `stepout` command
**Goal:** a built wheel runs with no Node and no checkout.
**Files:** `pyproject.toml`, `web/vite.config.*` (build into the package), `channels/web.py` (`DIST`), `app.py` (entry), `src/stepout/__init__.py` (version).
**Approach:**
- Page build output lands in `src/stepout/_web/`, included as package data. `DIST` tries the package folder, then `web/dist`.
- `[project.scripts] stepout = "stepout.app:cli"`: no argument starts the web chat and opens the browser; `stepout cli` is the terminal chat; `python -m stepout.app web` keeps working.
- `mem0ai` becomes the extra `stepout[mem0]`. `memory.build` already imports it lazily and falls back to plain files with a line saying why; extend that line to say how to install the extra.
**Verification:** `uv build`, install the wheel into a temp venv, start it, `GET /` returns the page and `GET /api/conversations` returns `[]`; scripted by a smoke script used again in U3.

### U3. Release pipeline
**Goal:** a tag produces a wheel with the page inside and proves it installs clean.
**Files:** `.github/workflows/release.yml`, `scripts/smoke_install.py`, README quick start.
**Approach:**
- On tag: Node build of the page, `uv build`, run `smoke_install.py` on `windows-latest` (a machine with nothing of ours), attach the wheel to the Release.
- The README's first block becomes the install line pointing at the Release asset.
**Verification:** a dry-run tag on a fork or branch; the smoke script passes on the runner.

### U4. `stepout init`
**Goal:** key and folders without touching a file.
**Files:** new `src/stepout/init.py`, `app.py` (call on first run), `grants.example.toml` (wording), tests.
**Approach:**
- Key read with hidden input, checked with a call that costs nothing (`models.list`, see Verify first), written to `<home>/.env`. It is never echoed or logged.
- Folders are chosen by `stepout grant`, which `init` calls and which can be run again any time (Key Decision 7): offers Documents, Downloads and Desktop that exist, or "another folder or drive". For a drive or folder it lists the **top-level folders** with a tick each (off-limits ones are left out and counted), then asks the mode per choice: `metadata` (names, sizes, dates, counts; the default) or `read` (also file text, which goes to the model provider and closes the web for that task; said in those words). Writes `<home>/config/grants.toml`, one grant per ticked folder.
- A whole drive or profile root is allowed only after typing its name to confirm; `find` on a drive root is already refused by Files, so per-folder grants work better and are the default.
- `stepout grant` also lists and removes grants. The "no folders are allowed yet" sentence in `files.py` points at it instead of "copy grants.example.toml".
- Runs by itself when the key or grants are missing ("Set up now? [Y/n]"); `stepout init` reruns it. Idempotent; shows what exists and asks before changing it.
- Other providers: `stepout init --provider openrouter` asks for that key and writes the two tier lines. Optional, small.
**Verification:** scripted-input tests; the key never appears in captured output or the log; a bad key says so in plain words and writes nothing.

### U5. Edge fallback and fail-closed Files
**Goal:** no "install Chrome" step on Windows; no false safety elsewhere.
**Files:** `browser.py`, `files.py`, tests.
**Approach:**
- Try `chrome`, then `msedge`; the "not found" message names both.
- `Files.from_config` returns "no file access on this system yet" off Windows.
**Verification:** unit tests with a fake launcher; one real run of the live view on Edge (Verify first).

**M1 check:** from a machine with only `uv`: the install line, paste a key, say yes to one folder, ask a question, get the answer.

### U6. Remote guard (ADR first)
**Goal:** the page can be served under a Tailscale name without opening the door wider than that name and its owner.
**Files:** `channels/web.py`, `docs/ui-contract.md` (Security), new ADR, tests.
**Approach:**
- `STEPOUT_REMOTE_HOSTS`: exact names, no wildcards, written by `stepout remote`. Adds `Host: name` and `Origin: https://name` to the allowed sets.
- If remote hosts are set, a request that arrived under one of them must carry the owner's Tailscale login header (recorded by `stepout remote`); any other login gets 403.
- Direct `127.0.0.1` requests behave exactly as today.
**Verification:** tests: unknown host 403; known host without the header 403; wrong login 403; right login 200; localhost unchanged; no wildcard accepted.

### U7. `stepout remote`
**Goal:** R7, R8, R10.
**Files:** new `src/stepout/remote.py`, `app.py`, tests.
**Approach:**
- Reads `tailscale status --json`; states: not installed (prints the download link and the winget line), needs login, ready. Finds `tailscale.exe` even when it is not on PATH.
- Asks for a neutral machine name (HTTPS puts it in a public certificate log), then runs `tailscale serve --bg` to `localhost:<port>`.
- Prints the URL and a QR code. `stepout remote off` undoes it.
- Keeps the laptop awake while the app runs (Windows execution-state call; lid-closed still sleeps, and the output says so).
- Never calls `funnel`; a test greps for it.
**Verification:** run against a fake `tailscale` for each state; the real thing on this laptop with the owner's account (the spike, first).

### U8. Phone polish
**Goal:** R9.
**Files:** `web/` (manifest, icon, header), `channels/web.py` (name in `hello`), `docs/ui-contract.md`.
**Approach:** a web manifest and icon so "Add to Home Screen" works; the laptop's name in the page header; the page's reconnect state shown when the link drops.
**Verification:** in the real page at 375 px (CLAUDE.md: not only over the WebSocket); the page's tests and the mock server updated.

### U10. Folders panel and Explorer menu (optional, after M2)
**Goal:** give many folders in a few clicks, like Drive's "Upload folder".
**Files:** `channels/web.py` (a local-only route), new `src/stepout/folder_dialog.py`, `web/` (panel), a small `winreg` helper, `docs/ui-contract.md`, tests.
**Approach:**
- One `grant(paths, mode)` function is the only writer of `grants.toml`; the terminal (U4), the panel and the Explorer menu all call it.
- "Add folders…" asks the laptop to open a native folder dialog; the chosen folder's top-level sub-folders come back as a tick list with Select all and one mode for all. Off-limits folders are counted, never listed.
- "My usual folders" uses Windows known folders (so a OneDrive-moved Documents is found). "Whole profile" and a whole drive need the name typed.
- Explorer right-click "Allow Stepout here": a per-user registry entry offered once by `init`, removable with one command; it calls `stepout grant "<folder>"`.
- The route refuses any request that arrived under a remote host or carried a remote login header, and the dialog is brought to the front.
**Verification:** tests that a remote-host request is refused and that `grant()` rejects off-limits and non-local paths; a spike on the real dialog (multi-select, focus); the real page at 375 px shows the "do this on the laptop" state.

### U9. Docs
**Goal:** the README says three steps and is true.
**Files:** `README.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/history.md`, ADRs for U1/U2 (install layout) and U6 (remote access).
**Verification:** a person who has not seen the repo follows only the README on a clean machine.

## Verify First

Not confirmed from docs yet; each is checked at the unit named:

- `tailscale serve --bg localhost:<port>` syntax, how HTTPS gets enabled the first time, and the exact identity header names (U6, U7 spike).
- The `Host` header our server sees through Serve (U6).
- `uv` runs a console script from a Release wheel URL, and the URL form that keeps the install line short (U3).
- `models.list` needs no credit and works with a fresh key (U4).
- Edge supports `page.screencast`, which the live view uses (U5).
- The winget id for Tailscale, and Chrome on the GitHub Windows runner (U3, U7).

## Risks

| Risk | Handling |
|---|---|
| Existing users' `./data` is not found by an installed copy | `STEPOUT_HOME` points at it; no silent move. Documented in U9. |
| A home folder outside the repo widens what the agents could reach | U1 blocks it; R4 has a test. |
| The tailnet holds another person's device | U6's login header check. |
| Tailscale's CLI or headers differ from what we assume | U7 starts with a spike on a real account. |
| Plan details of the free Tailscale plan change | Check its plans page when writing U9. |
| Pydantic AI moves fast | Already pinned `>=2.54,<3`. |

## Open Questions

1. **Repo owner, name and visibility:** the install line needs them.
2. **PyPI too?** `uvx stepout` is the shortest line, but it is a public name claim. Release wheel only until you say so.
3. **Windows only for the file hands, for now?** Assumed yes.

## Done When

1. On a machine with only `uv` and Chrome or Edge: one command, a key, one folder, and an answer, in under five minutes and with no file edited by hand.
2. The install smoke test passes on a clean Windows runner for every tag.
3. `stepout remote` on a machine with no Tailscale ends at a QR code, and a phone that scans it sees the chat.
4. A request with a wrong host or a wrong Tailscale login is refused.
5. The agents cannot read the new home folder.
6. The offline suite and the page's tests are green.
