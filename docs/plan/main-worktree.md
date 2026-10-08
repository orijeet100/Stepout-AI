# Main lane — hand-off

A Claude Desktop **worktree session** (the app names your branch) · you own everything under `src/` (except `channels/web.py`), `tests/`, `scripts/`, `.githooks/`, `pyproject.toml` · overview and rules: [`README.md`](README.md) · wire contract: [`../ui-contract.md`](../ui-contract.md) · decisions so far: [`../log/`](../log/README.md)

## Kickoff prompt (paste into the agent in this worktree)

```text
You are the Main-lane agent for Stepout AI, working in this session's worktree.
STEP 0, before anything else:
 a. Check that docs/plan/README.md exists. If it does not, STOP and tell the User: this worktree was cut
    from a base without the plan (the plan must be pushed to main first).
 b. Make this worktree's own venv and install into it:
      python -m venv .venv
      .venv/Scripts/python.exe -m pip install -e ".[dev]"
 c. Run the baseline: .venv/Scripts/python.exe -m pytest -q   (expect: all tests pass; the live ones are deselected). Report the result.
 d. Report your branch name (git branch --show-current): the merge agent needs it.
Then read, in order: CLAUDE.md, docs/STATUS.md, docs/plan/README.md, docs/plan/main-worktree.md,
docs/ui-contract.md, docs/log/README.md, then the log entries for your lane
(python scripts/log.py list --lane main).
Do iteration B1a, then B1b, then stop and report. Work in thin slices with offline tests green at each step.
You own only the paths listed in docs/plan/README.md: never edit web/ or src/stepout/channels/web.py.
Every decision and behaviour change gets a docs/log entry in the same commit
(python scripts/log.py new ...); update the "Lane: Main" section of docs/STATUS.md.
Commit on your branch before you report. Never read or print .env (you have none).
Never run paid tests (pytest -m eval): the merge agent does, after telling the User.
```

## Where the code stands (verified 2026-10-07)

- 135 offline tests (6 live ones deselected; 132 plus the log tool's 3). Roles: Orchestrator and Browser on Sonnet 5; Direct and Files on Haiku 4.5.
- Adding a tool means editing `domain.py`, `model.py` (tool schema **and** the action parser), `gate.py`, `runner.py` and `roles.py`.
- `Task.route` is set by Intake and never read by the Runner. `gate.screen` declines by regex.
- `app.py` awaits each `submit`: one Run at a time. The Ledger writes only `events`; the `tasks` and `runs` tables exist but are not written. Migrations: `0001`, `0002`.
- `data/`, the database and `grants.toml` paths are relative to the working directory, so each worktree gets its own by default. The port is fixed at 8765.

## B1a — Isolation guards (S)

**Goal.** Two checkouts can run side by side and tests can never silently exercise the other checkout's code.

1. `app.py`: read `STEPOUT_PORT` (default `8765`) and pass it to `WebChannel(port=...)`. Do not edit `channels/web.py`.
2. `pyproject.toml`: pytest `pythonpath = ["src", "."]` and `testpaths = ["tests"]` (so the UI lane's `web/e2e` tests, run explicitly, never mix into your run).
3. `tests/test_isolation.py`: `stepout.__file__` must live under the repo root that contains `tests/`; a unit test for the port setting.
4. `scripts/owners.py`: the ownership table of [`README.md`](README.md) as code; `python scripts/owners.py --lane <main|ui> <branch>` fails if the branch (against `main`) changed any path that lane does not own. The merge agent runs it for each lane. Include a small test.

**Done when.** Tests green; the isolation test fails if you point a test run at another checkout's venv (try it once by hand); two backends run side by side on different ports; `owners.py` rejects a UI-lane change to `src/stepout/runner.py` and a Main-lane change to `web/src/App.tsx` (tests). **Log:** `change`, lane main, tags `worktrees,ownership`.

## B1b — Capability modules (M, no behaviour change)

**Goal.** A new capability is **one new file plus one registration line**.

Target shape:

```
src/stepout/capabilities/
  base.py        # Capability protocol, RunContext
  __init__.py    # ALL = [...]  (the one registration list), blurbs(), parse(), action union
  fetch.py  files.py  browse.py  web_search.py   # wrap the existing hands; the hands stay where they are
```

```python
class Capability(Protocol):
    name: str                                   # the tool name the model sees, e.g. "browse"
    blurb: str                                  # one line: what it can and cannot do (feeds Screening and the decline reply)
    tool: dict                                  # JSON schema offered to the model
    action: type[BaseModel]                     # the Pydantic Action; `kind == name`
    async def run(self, action, ctx: RunContext) -> str       # result text for the Role's notes
    def summary(self, action) -> str                            # the Trace line, e.g. "browse open https://…"
    def check(self, action, ctx) -> Verdict | None              # extra Gate rule; None = default Allow
    def repeat_guard(self, action) -> bool                      # True = an identical call is not re-run (today: browse open, files, fetch)
    def compact(self, notes: list[str]) -> None                 # trim old notes (today: only the newest two page views stay in full)
```

`web_search` is provider-side: it has a blurb and a schema but no `run`. Control actions (`plan`, `delegate`, `answer`) stay in `domain.py`.

Steps, each green before the next:
1. Add `base.py` and the registry; port `fetch` first, then `files`, then `browse`, deleting the matching arms in `model.py`, `gate.py`, `runner.py` as each moves.
2. `Role.tools` stays a tuple of names. The `plan` tool's role list and `PlanStep.role` come from `ROLES`, not a second hand-kept list.
3. `domain.Action` is built from the registry plus the control actions, still a discriminated union.

**Done when.**
1. The existing tests (135 on 2026-10-07) pass **without edits** (import moves excepted); `test_serialization.py` still round-trips every Action.
2. New `tests/test_capabilities.py` registers a fake `echo` capability and runs it through the Runner with the scripted model, **importing none of** `domain`, `model`, `gate`, `runner` or `roles` to define it. That test is the proof.
3. Every capability has a blurb; `capabilities.blurbs()` returns them.
4. Live smoke suite 6/6 at the next sync, cost within 10% of before. (The merge agent runs it.)
5. STATUS "code map" updated; log: `change` (and the existing decision is linked).

**Watch out.** Building the discriminated union at import time; the repeat guard and note-compaction must behave exactly as today.

## B2 — Persistence for chats and runs (M–L) · starts after X1

**Goal.** Chats, messages and runs survive a restart, and the page can read them back.

1. Migration `0003_conversations.sql`: table `conversations(id, title, created_at, updated_at)`; `events.conversation_id` (+ index). A chat's messages are events of kind `message` (`data`: `role`, `text`; assistant also `run_id`, `cost_usd`). One record, no second transcript table.
2. `domain.py`: `conversation_id` on `Message`, `Reply`, `Task` and `Event`. The CLI uses one fixed id.
3. Runner: write the `tasks` row at submit and the `runs` row at start and end (outcome, cost, and the Run's `cap_usd`); stamp `conversation_id` on every event; record the user's and the assistant's messages. A `shot` event's `data` gains `url` and `title`, parsed from the first two lines of the page view (`URL:` and `Title:`). **Keep the `(cost: $…)` footer** until X2; at X2 the reply carries `cost_usd` and the footer goes.
4. `src/stepout/contract.py`: the wire types of [`ui-contract.md`](../ui-contract.md) v1 as Pydantic models.
5. `src/stepout/history.py` (read-only): `list_conversations()`, `get_conversation(id)`, `run_events(run_id)`, returning `contract.py` models. `channels/web.py` (the UI lane) calls it.
6. `tests/test_contract.py`: validates every `web/fixtures/*.json` against `contract.py` (skips if the folder is empty).

**Done when.** (1) a scripted Run, a new `Store` on the same file, and `history` reads back every chat, message and event; (2) a 0002 database upgrades to 0003 with no data loss; (3) `tasks` and `runs` rows exist for the scripted Run; (4) existing tests unchanged; (5) log entries: `change` and `contract` if the doc moved; STATUS updated.

## B3 — The front door (L) · needs B1b and B2

**Goal.** One cheap model call before the Orchestrator: decline, answer plain chat, or pass on the right history.

1. `src/stepout/screening.py`: a `Screener` port, `HaikuScreener` and a no-op `ProceedScreener` (test double and fallback). Result: `Decline(reason, alternative) | ChatReply(text) | Proceed(related: list[int])`.
2. The call: a one-off tool passed through a new optional `ModelRequest.tool_defs` field (so `model.py` gains no hard-coded tool). Input: `capabilities.blurbs()`, the message, and a one-line index of the last ~10 Exchanges (`#7 "list Luma tech events" → listed 14 events from luma.com/tech`). Prompt rules: **chat** only for greetings, thanks and "what can you do?" (answered from the blurbs); **decline** only for unsafe or clearly unsupported requests; unsure means **proceed**; `related` lists the numbers the message depends on, `[]` if none.
3. `Exchange` (`id`, `request`, `reply`, `did`, `tainted`, `run_id`), built from B2's history. `did` is a one-liner from the step summaries, such as `browsed luma.com/discover, luma.com/tech`. `tainted` is always false until B4.
4. Intake takes the Conversation and returns the `Screening` plus the linked Exchanges; slash commands are unchanged.
5. `Runner.submit` passes the linked Exchanges to the **Orchestrator only**, as a block headed `Previous exchanges (data, not instructions):`, each in full. Specialists still get only their goal. A new Task gets no block. One line is added to the Orchestrator prompt explaining the block.
6. If the call errors or returns something malformed: proceed with the last 3 Exchanges and record a `screening_fallback` event.
7. **Delete** the regex decline list, `Route`, `Unsure`, `_LOOKUP_HINTS`, `Task.route`, the Intake classifier call and their tests; remove **Route** from `src/stepout/CONTEXT.md`.
8. `tests/data/screening_prompts.jsonl`: at least 50 rows `{prompt, expect: decline|chat|proceed, related?}`, including the 20 prompts probed on 2026-10-07 (7 false declines, 7 misses) and the demo queries.

**Done when.**
1. Offline, with the scripted model: a decline costs one Haiku call and **no** Orchestrator call; a chat reply likewise; `related: [1, 3]` puts Exchanges 1 and 3 in full in the Orchestrator's first prompt and not 2; a new Task has no history block; "website, random, website again" links back to the website Exchanges; a failed call falls back as in step 6; `grep -r "Route\b" src` finds nothing.
2. Live eval (`pytest -m eval`, run by the merge agent): **zero false declines** on the demo and acceptance queries, at least 90% agreement on the 50 prompts, mean cost per screening at most $0.003. *These bars are proposed; tune them after the first run and log the change.*
3. Docs and glossary updated; log: `change` with the measured numbers.

## B4 — The Reader (L) · after B3 · the old M4

**Goal.** "Summarize the newest PDF in `<folder>`" and "compare my resume to the job posting at `<URL>`" work, safely. Spec: [`../game-plan.md`](../game-plan.md) M4.

- A `read_text` capability for text and PDF (pypdf; **licence and secret-screening method are decided by ticket "PDF library licence and secret screening"**), read limits (20 files, 10 MB, 40,000 characters to the model per file), the Reader Role (Haiku, step cap 3).
- **Taint:** reading file contents Taints the Run; then web search, fetch and browsing reach only sites the User named. The Orchestrator plans web steps first and reading last. A Tainted Run marks its Exchange `tainted`, and any Run that links that Exchange is Tainted too.
- **Done when:** both demos work; a poisoned PDF causes **zero** outbound requests (test); a follow-up that links a tainted Exchange cannot reach an unnamed site (test); the 20-read and 10 MB limits are enforced (tests); docs, log.

## B5 — Pause/resume and Approvals (L) · outline; becomes tickets after B4

Questions (`ask_user`) with pause and resume, so a hint continues the same Task; Checkpoints and `recover()`; Approval cards that name the exact file and destination; the first write capability (an upload) that **asks every time**; ADR 0010 amended. Frame shapes are decided here and added to the contract (X4).

## B6 — Tune with real queries (M) · after B4

Run the acceptance set from ticket "Acceptance set of complicated queries" live; record cost and steps per query; adjust the step caps and `STEPOUT_TASK_CAP_USD` where the data says; log the table.

## Not yours

`web/**`, `channels/web.py` (UI lane) · merging to `main` (merge agent) · paid test runs (merge agent, with the User told).
