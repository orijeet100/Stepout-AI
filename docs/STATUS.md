# Stepout AI — status and handoff (read this first)

Updated 2026-10-07 · after milestone M3 · `main` is the only branch.

**What it is.** A task agent you drive from a chat page (Telegram later). An **Orchestrator** plans each request and hands steps to specialist agents that each hold one hand: web search, a headless browser, the disk's file names. It reports back while you watch every step live. **Claim to prove (later):** human interventions per task fall across repeated attempts versus a memory-off control; no model training, recall only ([ADR 0004](adr/0004-drop-zero-model-replay.md)).

## Where we are

| Milestone | Built and verified | Result |
|---|---|---|
| **S1** domain core | Intake, Gate, Runner, Fetcher, Ledger/Store, CLI | live: decline $0, "2+3" $0.02, NYC news $0.26 (single loop) |
| **web chat** | Vite + React page, aiohttp WebSocket channel (localhost, origin-checked) | works; found and fixed a `tools=null` API bug |
| **M1** Orchestrator | one loop, Role table, Plan, shared $1 Budget, Stop, live Trace, source links | NYC news $0.068 (4× cheaper); Stop works |
| **M2** Files | `list`/`find`/`count`, real-path resolution, fixed block list, `grants.toml`, 60 s walks | real D: drive: 1.6M files counted, PARTIAL; `.env` refused; "find my resume" asks for a hint, then finds it ($0.034) |
| **M3** Browser | headless installed Chrome, read-only, every request and redirect hop policed, screenshots in the trace | zero requests reach a private server by any route; live smoke suite 6/6 |

**Tests:** 132 offline (`pytest -q`, includes real Chrome) + 6 live smoke tasks (`pytest -m eval`, about $0.11). **Next: M4 (Reader)**, then S3 Approvals.

## Run, test, verify
```bash
./.venv/Scripts/python.exe -m pytest -q                                        # offline, scripted model
./.venv/Scripts/python.exe -X utf8 -m pytest -m eval -s tests/test_live.py     # real API + Chrome + disk, prints calls and $ per task
./.venv/Scripts/python.exe -m stepout.app web                                  # chat at http://127.0.0.1:8765 (or no arg: terminal)
cd web && npm install && npm run build                                         # after editing the page
```
Setup: `.env` with `ANTHROPIC_API_KEY` (never read or print it); `data/config/grants.toml` from `grants.example.toml` (only the User edits it). Gitignored: `.env`, `data/`, `.archify/`, `graphify-out/`, `.claude/settings.local.json`. Restart the server after changing Python.

## How it fits together
```mermaid
flowchart LR
    You(["You"]) --> Channel["Channel ✓<br/>web chat · CLI"] --> App["app ✓"] --> Intake["Intake ✓<br/>screen · cheap route"]
    Intake -->|Task| Orch["Orchestrator ✓<br/>plan · delegate · report"]
    Orch -->|reply · live Trace| Channel
    Orch --> Direct["Direct ✓<br/>search · fetch"] & BrowserA["Browser agent ✓"] & FilesA["Files agent ✓"] & ReaderA["Reader · M4"]
    Direct & BrowserA & FilesA & ReaderA -->|every Action| Gate{{"Gate ✓<br/>Allow · Refuse"}}
    Gate --> Fetcher["Fetcher ✓"] --> Web[("Websites")]
    Gate --> Chrome["Browser ✓<br/>headless Chrome"] --> Web
    Gate --> FilesM["Files ✓<br/>grants · block list"] --> Disk[("Your disks")]
    Gate -.-> ReadText["read_text · M4"] -.-> Disk
    Orch -.->|every step| Ledger["Ledger ✓"] -.-> Store[("SQLite")]
    Orch --> API["Anthropic API<br/>every Role's calls"]
    classDef planned stroke-dasharray: 5 5
    class ReaderA,ReadText planned
```
✓ built · dashed = planned. Design-level detail: [`architecture.md`](architecture.md) (target design; this file is the reality).

| Code | Job |
|---|---|
| `runner.py` | the one agent loop for every Role; shared Budget/Gate/Ledger; plan auto-starts its first step; Stop; repeat guard |
| `roles.py` | Role table: prompt, tools, model, step cap (Orchestrator Sonnet 5, Direct Haiku 4.5, Files Haiku 4.5, Browser Sonnet 5) |
| `model.py` | Anthropic adapter; tools `plan delegate answer fetch files browse`; citations → Sources list |
| `gate.py` | `screen` (before spend) and `check(action, role's kinds)` |
| `files.py` / `browser.py` / `fetch.py` | the hands; each enforces its own path or network policy |
| `intake.py`, `ledger.py`, `store.py`, `domain.py` | routing + decline, append-only events (role, parent), SQLite with tracked migrations, plain-data types |
| `channels/web.py`, `channels/cli.py`, `app.py`, `web/` | channels (trace out, Stop in, screenshot route), wiring, the React page |

## Decisions (and where to read more)

| Decision | Why | Where |
|---|---|---|
| Build the parts we measure; borrow plumbing (Playwright, Anthropic SDK, Pydantic, aiohttp); no agent framework | learn how agents work | ADR 0001 |
| V0 = one Python process on the laptop; no Docker/cloud/credentials/email | scope | ADR 0002 |
| Memory = plain files first; mem0 later as a measured challenger | measurable | ADR 0003 |
| Zero-model replay dropped; headline metric is interventions per task | honest claim | ADR 0004 |
| Two contexts: Assistant and Evaluation (evaluation never grades itself) | trust | ADR 0005 |
| SQLite; one `Store`; migrations tracked by `PRAGMA user_version` | simple, Postgres later | ADR 0006 |
| Actions/Results are plain serializable data | hands can move off-laptop in V1 | ADR 0007 |
| Laptop files only through Grants + fixed block list | safety | ADR 0008 |
| The web page is React (Vite + TS) served by the Python process | not thrown away | ADR 0009 |
| **One loop, five Roles**; Orchestrator plans as data (no separate Planner); only it talks to the User; Findings are untrusted; one Gate/Budget/Taint/Ledger per Run | context isolation, least privilege, one agent in charge of the log | ADR 0010 |
| V0-basic is **read-only**: no typing, submitting, uploading, downloading, deleting | no Approvals yet | ADR 0010 |
| $1 per Run shared by all Roles, at most 3 web searches | cost control | ADR 0010 |
| Headless fresh Chrome via the installed Chrome; never the User's everyday Chrome | their logins stay out of reach | ADR 0010 |
| Whole C: and D: granted in read mode, minus the block list (`.ssh`, `.env`, keys, browser profiles, Windows credentials, Windows, Program Files, the Assistant's own folder) | the User's call; secrets stay out | `grants.toml`, `files.py` |
| **No full-drive scans:** `find` refuses a drive root; counts stop at 60 s and say PARTIAL; when unsure the agent asks which folder | the User's call; smarter search later | `files.py`, game-plan "Later" |
| After a file's contents are read, web access is limited to sites the User named (M4) | exfiltration through URLs | ADR 0010, FR45 |
| Computer use is out of V0 | the Gate can't judge pixel clicks | ADR 0010 |
| API facts: no forced `tool_choice` (newer models reject it); basic `web_search_20250305` (the 2026 versions need code execution, Haiku can't); `max_uses` = searches left | read from the official docs | `model.py` |
| Orchestration efficiency: a plan starts its first step; every Role's state ends "results are above, answer if enough"; repeated identical hand actions are not re-run; only a Role's newest two page views stay in its notes | 1–4 calls per simple task | `runner.py` |
| Browser safety: `route.fetch(max_redirects=0)`, redirect hops checked by us, page WebSockets and media blocked, DNS verdict per host:port | Playwright follows redirects itself | `browser.py` |
| Trace = the Ledger's events streamed live; Stop = a flag checked between steps and inside walks | visibility | `runner.py`, `channels/` |
| Process: thin vertical slices, tests + a live check each, docs in the same commit, third-party skills only if used (`docs/third-party.md`), public repo: no secrets or personal paths in git | | `CLAUDE.md` |

## Remaining, in order
> **Replanned 2026-10-07:** the order of work is now [`plan/README.md`](plan/README.md) (two lanes, iterations B1–B6 and U1–U6). The Reader below is iteration B4; Approvals and pause/resume are B5. The list below is the older view; each lane's progress is in its section further down.

1. **M4 Reader** — `read_text` for text and PDF (pypdf; check its licence), secret screening, 20 reads/10 MB/40k chars per Run, Taint, and the "no web after a read" rule; demos: summarize the newest PDF; compare my resume to a job posting.
2. **S3 Approvals + pause/resume** — Questions, Approvals, Checkpoints, `recover()`: needed for uploads and form filling, and so a hint like "it's in the 2026 resume folder" continues the same task (today it arrives as a new request with no memory).
3. S4 Telegram · S5 Memory (recall, Persona, Notes) · S6/S7 Evaluation and the security suite (one loop vs orchestrated is a Condition) · S9 persona editor · S10 mem0 · S11 organize files. See [`roadmap.md`](roadmap.md).
4. Ideas parked: smarter file search (ask with options, rank folders, prune `node_modules`/`.git`/venvs, fuzzy names), a Verifier before replying, a separate Planner and parallel steps (V1).

**Open questions:** secret screening method (patterns vs model) · PDF library licence · is a click Consequential (S3) · evaluation matrix vs the $25/month budget (S6).

## Known gaps (ceilings, not bugs)
Stop takes effect at the next step (up to ~20 s inside a long search) · a search ending in `pause_turn` is returned partial · a malformed tool call shows "Something went wrong" instead of being fed back · Intake's cost isn't in the reply total · chat/trace history lives in memory until restart · the Orchestrator sometimes over-plans · whole-drive counts are partial by design · names and paths from `list`/`find` go to the model API (counts don't) · a folder swapped for a link between resolve and walk isn't caught (walks never follow links) · screenshots in `data/runs/` are never cleaned up · subresource redirects are dropped, not followed.

## Gotchas for the next agent
Windows-only paths (`files.py`). Run tests with the venv Python. In generated Python, write Windows paths with `\\` (a bare `\D` is a `SyntaxWarning`; CI-style check: `pytest -W error::SyntaxWarning`). Use `-X utf8` when printing arrows to the console. The live suite and the web chat spend real money: say so before running them. `.archify/` holds generated diagrams (local only).

## Lane: Main
Not started. Next: B1a (isolation guards) and B1b (capability modules) — [`plan/main-worktree.md`](plan/main-worktree.md). Owner of this section: the Main lane.

## Lane: UI
**U1 built, waiting for the User's pick.** Three directions on one fixture screen at `#/design/a` (Paper), `/b` (Slate), `/c` (Ink); `?theme=light|dark`, `?viewer=N`. View: `cd web && npm run dev`, then http://localhost:5173/#/design/a. After the pick: its token block becomes `web/src/design/tokens.css`, the other two directions and the gallery are deleted, and a `decision` log entry (with screenshots) closes U1. Then U2 ([`plan/ui-worktree.md`](plan/ui-worktree.md)). The lane has its own venv (`.venv`) and `web/node_modules`; the UI/UX Pro Max skill is installed locally and untracked ([log](log/2026-10-07-ui-ux-pro-max-skill-used-for-u1-installed-locally-and-not-co.md)). Owner of this section: the UI lane.

## Files
[`plan/`](plan/README.md) (two-lane plan, hand-offs) · [`ui-contract.md`](ui-contract.md) (page ↔ backend) · [`log/`](log/README.md) (every decision and change; `python scripts/log.py list`) · [`requirements.md`](requirements.md) (FR/NFR, acceptance script) · [`architecture.md`](architecture.md) · [`game-plan.md`](game-plan.md) (V0-basic milestones) · [`roadmap.md`](roadmap.md) (slices S0–S11) · [`adr/`](adr/) · [`third-party.md`](third-party.md) · glossaries: [`../CONTEXT-MAP.md`](../CONTEXT-MAP.md), `src/stepout/CONTEXT.md`, `tests/eval/CONTEXT.md`.
