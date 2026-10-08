# Architecture — V0

Status: draft for sign-off · Date: 2026-10-07 · Language: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md) · Requirements: [`requirements.md`](requirements.md) · Order of work: [`roadmap.md`](roadmap.md)

One Python process on the laptop. Two bounded contexts — **Assistant** (the product, `src/stepout/`) and **Evaluation** (the proof, `tests/eval/`) — see [ADR 0005](adr/0005-two-bounded-contexts.md). Design vocabulary: **module**, **interface**, **seam**, **adapter**, **depth** (leverage per unit of interface).

## 1. The shape

```
 Telegram ───┐
 React page ─┤                    ┌─► Gate  (pure rules; every Action gets a Verdict)
 Terminal ───┼─► Channel ─► app ─► Intake ─► Runner ─┼─► Browser ───► websites
 Simulated ──┘   (interface)         │               ├─► Fetcher ───► websites
 user (eval)                         ▼               ├─► Files ─────► your folders (Grants)
                                   Model             ├─► Memory ────► data/memory/
                                  (port)             └─► Ledger ────► Store ─► data/stepout.db
                                     │                  (Runner also keeps run state in Store)
                                     └─► model provider

 Evaluation (tests/eval) drives the Channel as the Simulated user and reads the Ledger.
```

The dependency rule: arrows point inward to `Gate` and the domain types. Nothing in the Assistant imports a Channel adapter except `app` (the composition root). Evaluation imports nothing from the Assistant except the Channel interface, the domain types and the Ledger reader. Inside the Runner, one loop runs under several Roles (see *Roles* in §2).

## 2. Modules

Each is **deep**: callers learn a small interface; the behaviour behind it is large.

| Module | Interface (all a caller learns) | Hides | Depends on |
|---|---|---|---|
| **Intake** | `read(message) → Reading` | fast paths (reply-to, buttons, `/commands`), Stale check, then the **front door** (`screening.py`): one cheap-model call that declines, answers plain chat, or lets the message through with the earlier Exchanges it depends on; if that call fails the message proceeds with the last three | Screener (Model), the chat's Exchanges (history), run state, clock |
| **Runner** | `submit(task)` · `deliver(answer \| approval \| cancel)` · `recover()` | the Run state machine, Steps, the agent loop and its Roles (an Orchestrator that Delegates to Direct, Browser and Files agents), tool dispatch, Budgets (including the read Budget), Checkpoints, at-most-once, Taint, Recollection at start, Memory writes at end, browser lifecycle | Model, Gate, Browser, Fetcher, Files, Memory, Ledger, Store, clock, `notify` |
| **Gate** | `check(action, ctx) → Verdict` | every rule: Risk classes, Forbidden list, navigation rules, Approved sites, Approval matching and expiry, Taint, Grants, Budget checks | nothing — pure functions |
| **Memory** | `recall(task) → Recollection` · `remember(item) → Remembered \| Rejected` · `forget(what) → count` | Provenance check, secret/PII redaction, Pinned entries, Note expiry, bounded recall, storage format | a store behind an **internal** seam (files now; mem0 in S10) |
| **Ledger** | `record(event)` · `query(run=None, since=None) → events` | schema, append-only rule, cost totals, references instead of contents | Store |
| **Browser** | `open() → session`; session `look() → PageView` · `do(action) → Result` · `close()` | Playwright, page views, screenshots, **network policy on every request including ones pages start themselves**, uploads from Grants, temp downloads, Chromium sandbox | Playwright |
| **Fetcher** | `get(url) → FetchedPage` | HTTP, the same network policy, HTML → text, size limits | httpx |
| **Files** | `find(query) · list(folder) · stat(folder) · read(path)` (S11: `plan` · `apply` · `undo`) | Grants and Modes, **Off-limits**, real-path resolution, PDF text extraction, secret screening, the Undo journal | Grants config, the local disk |
| **app** | `main()` | wiring, the receive → read → submit/deliver loop, commands (`/status`, `/stop`, `/forget`, `/persona`, `/retry`, `/undo`) | everything (composition root) |

**Store** is internal, not a module callers see: the one place holding the connection, the migrations and every SQL statement, used by Ledger and Runner. A move to Postgres touches this one file ([ADR 0006](adr/0006-sqlite-for-runs-and-ledger.md)).

**Deletion test, applied.** Delete Gate and its rules reappear inside every tool and route — keep. Delete Ledger and every module invents its own logging and cost math — keep. A separate "router" or "scope guard" module would only pass through to the model — folded into Intake. A separate "agent loop" next to a "run manager" would force the loop to expose its state for checkpointing — folded into Runner, with the Step as an internal seam its own tests can use. Files stays separate from Browser: Grants, Off-limits and path safety are a body of rules of their own.

### Roles — one loop, five of them ([ADR 0010](adr/0010-one-loop-many-roles.md))

The Runner has one agent loop. A **Role** is a system prompt, a tool set, a model and a Step cap; the loop function is the same for all of them. The **Orchestrator** receives the Task and has no hands — it writes a **Plan** (a short list of steps: Role, goal, status), `delegate`s one step at a time, re-plans if a step fails (at most twice), asks the User, and reports. A specialist runs the same loop with its own tools and hands back a **Finding**. See [`game-plan.md`](game-plan.md) for the milestones.

| Role | Tools (its one hand) | Works on | Slice |
|---|---|---|---|
| **Orchestrator** | `plan`, `delegate`, `ask_user`, `answer` — none of the hands | Findings, Recollection | M1 (S1b) |
| **Direct** | fetch, search (Fetcher) | public web pages | M1 (S1b) |
| **Files** | `list` · `find` · `count` (Files module — names, counts, sizes, dates; never contents) | folders inside Grants | M2 (S8) |
| **Browser** | read-only Actions of the Browser module (headless): navigate, read page, scroll, follow link | pages, in a browser | M3 (S2) |
| **Reader** | `read_text(path)` — text and PDF extraction, secret screening, truncation; only for paths the Orchestrator names | contents of files inside Grants | M4 (S8) |

```python
async def run_agent(role, goal, run):               # run = Budget, Taint, Approvals, Ledger ids
    spec = ROLES[role]
    transcript = [goal]
    for _ in range(spec.max_steps):
        action = (await model.call(spec.model, spec.system, transcript, spec.tools)).action
        verdict = gate.check(action, run.context)        # the same Gate for every Role
        ledger.record(role=role, parent=run.agent_id, action=action, verdict=verdict)
        match action:
            case Answer(text):         return Finding(text)               # untrusted
            case Delegate(r, goal2):   transcript += await run_agent(r, goal2, run.child())
            case AskUser(question):    raise Pause(question)              # the Runner asks, not the specialist
            case _:                    transcript += await execute(action, verdict)
```

Rules: every Action of every Role passes the one Gate; Budget, Taint, the Approval list and the Ledger are per Run, not per Role; delegation is one level deep; a Finding is Untrusted content; only the Runner talks to the User; Checkpoints save the active Role stack. V0-basic is read-only, and once a Run has read file contents, web search, fetch and browsing are limited to sites the User named. Every call, return, Action and Verdict streams to the page as the Trace. No computer use in V0. Every specialist has exactly one hand, so a Role can only be steered into what that hand can do.

## 3. Seams and adapters

A seam is only real when two adapters exist (production + test counts).

| Seam | Adapters | Dependency kind |
|---|---|---|
| **Channel** — `messages() → stream of Message` · `send(reply)` · `trace(event)` (live view of the Run) · `cancel` flag (Stop) | Telegram (S4), React web (S9), CLI (S1), Simulated user (Evaluation, S6) | external, owned translation |
| **Model** — `call(request) → response` (response carries tokens and money spent) | provider adapter (S1), scripted model (tests, S1) | true external → mocked in tests |
| **Memory store** (internal to Memory) | Markdown files (S5), mem0 (S10) | local; the rules stay above the seam |

**Deliberately not seams** (one adapter, tested with a local stand-in instead):
- **Browser** — tested with real Chromium against the Simulated web. No fake page driver: a fake drifts from real pages, and fast tests come from Gate, Intake and Memory, which need no browser.
- **Fetcher** — tested against the Simulated web.
- **Files** — the local disk, tested against a Simulated folder. In V1 the laptop helper becomes a second adapter and the seam turns real; Actions and Results are plain data from S1 so that costs little ([ADR 0007](adr/0007-brain-and-hands.md)).
- **Store** — SQLite in a temp file. Postgres becomes the second adapter when a second machine or many Users write.
- **Clock** — a `now` parameter, not an adapter.

## 4. Interfaces — invariants and error modes

```python
# Ports (real seams)
class Channel(Protocol):                 # Telegram · Web · CLI · Simulated user
    def messages(self) -> AsyncIterator[Message]: ...
    async def send(self, reply: Reply) -> None: ...

class Model(Protocol):                   # provider adapter · scripted model
    async def call(self, request: ModelRequest) -> ModelResponse: ...

# Deep modules
class Intake:
    async def read(self, message: Message) -> Reading: ...
    # Reading = NewTask(request, previous Exchanges) | Chat(text) | AnswerTo(question) | ApprovalGiven(approval, yes)
    #         | Correction(task) | Command(name, args) | Declined(reason, alternative)
    #         | Stale(message) | Unclear(choices)

class Runner:
    async def submit(self, task: Task) -> None: ...
    async def deliver(self, reply: AnswerTo | ApprovalGiven | Cancel) -> None: ...
    async def recover(self) -> None: ...          # on startup

def check(action: Action, ctx: GateContext) -> Verdict: ...      # Allow | Ask(approval) | Refuse(reason)

class Memory:
    def recall(self, task: Task) -> Recollection: ...
    def remember(self, item: MemoryItem) -> Remembered | Rejected: ...
    def forget(self, what: str) -> int: ...

class Files:
    def find(self, query: str) -> list[FileRef] | Denied: ...
    def list(self, folder: Path) -> list[FileRef] | Denied: ...
    def stat(self, folder: Path) -> FolderStats | Denied: ...        # counts by type, sizes, dates
    def read(self, path: Path) -> FileText | Denied: ...             # Mode >= read; screened
    # S11: plan(folder, goal) -> Plan · apply(plan) -> Applied · undo(run) -> Undone
```

- **Actions and Results are plain serializable data** (Pydantic models; no live objects, handles or callbacks), with a round-trip test. This is what lets Browser and Files run elsewhere in V1.
- **Intake** — Messages from anyone but the User never reach it (the adapter drops them; Intake asserts). Fast paths run before any model call: a reply to a Question is an `AnswerTo`, a button is an `ApprovalGiven`, `/x` is a `Command`. Free text while a Run is paused and unclear → `Unclear` (two buttons: "answer to the current Task" / "new Task"). `screen` runs before money is spent; the model is asked only when `screen` says `Unsure`. Error: model unreachable → the Message waits and is re-read later.
- **Runner** — one Run executes at a time; others queue. Every Action passes `check` before it happens. A Consequential Action is written as *intended* in the same transaction as the Checkpoint, then *done* after — a crash in between makes the Outcome **Uncertain**, and the Action is never repeated; a unique constraint on (run, step, action) enforces it. Budget (money, Steps, time, files read) is checked before every model call and every file read. Recollection is taken once, at Run start; Memory is written only from the User's Answers and the Run's own Outcome. Reading file contents sets the Run **Tainted**. Errors: Budget reached → Question; Blocker → Blocked; malformed model output → one retry, then Failed; browser crash → resume once from the Checkpoint with a fresh browser, then Failed; no Answer for 24 h → Expired. **Roles:** Actions from every Role pass the same `check`; Budget, Taint and Approvals are shared across the Run; a specialist's Question or Approval is raised by the Runner, never sent by the specialist; a Finding is Untrusted content.
- **Gate** — pure and total: every Action gets a Verdict. Forbidden and Off-limits beat everything. Unknown Risk → Ask. An Approval matches one exact Action (same kind, target, values) and expires after ~15 min. In a Tainted Run every outward Action → Ask, with the exact data and destination. Navigation allowed only to `http(s)` on public hosts.
- **Memory** — rejects items whose Provenance isn't a User Message or a Run Outcome. Redacts card numbers, national IDs, bank details and passwords before writing. Never overwrites a Pinned entry. Expired Notes are never recalled. Recall is bounded.
- **Ledger** — append-only. Holds references to Persona facts and files, never their contents. Every model call has tokens and cost; every file opened has a path and size.
- **Browser** — enforces the network policy on **every** request (redirects, iframes, page scripts), not only on the Assistant's own Actions. Uploads only files the Gate has allowed from a Grant. Downloads go to a temp folder.
- **Files** — resolves the real path first, then checks Off-limits, then the Grant and its Mode; `Denied(reason)` otherwise. Rejects `..`, symlinks, junctions and network paths. Never returns contents in `metadata` Mode. Never writes in V0 (until S11). Screens contents for secrets before returning them. The Runner counts reads against the Budget (it `stat`s before it reads).

## 5. A Message's journey

```
You: "upload my resume to this job form" ─► Telegram adapter ─► app
app ─► Intake.read ─► NewTask(previous = [])                            [front door: one cheap-model call]
app ─► Runner.submit(task)  ─► the Orchestrator Delegates: the resume lookup to the Files Role, the form to the Browser Role
                              (each runs the loop below with its own tools and returns a Finding)
  Runner: Memory.recall ─► Recollection (Persona: name, email, resume lives at …\Resume\cv.pdf)
  each Step:
    Model.call(transcript) ─► proposes an Action                       [strong model]
    Gate.check(action)
      Allow  ─► Browser.do / Files.find ─► result ─► Checkpoint + Ledger
      Ask    ─► Approval sent with the exact file, size and destination ─► PAUSE
      Refuse ─► the model is told why; the Run continues or ends
    Model needs a phone number ─► Question sent ─► PAUSE
You: "+1 555 …" ─► Intake.read ─► AnswerTo(question) ─► Runner.deliver ─► RESUME from Checkpoint
You tap Approve ─► ApprovalGiven ─► Runner.deliver ─► Browser.do(upload, submit)
Run ends Done ─► Memory.remember(phone, from your Answer · where the resume lives · Note about the site)
              ─► result sent to you
```

## 6. A Run's states

```
queued ─► running ─┬─ Question ─► waiting_for_user ──── Answer ─────┐
              ▲    ├─ Ask ──────► waiting_for_approval ─ Approval ──┤
              │    │                     │ (24 h)                    │
              │    │                     └──► expired                │
              └────┼──────────── Resume from Checkpoint ◄────────────┘
                   ├─► done · blocked · failed · over_budget · cancelled
                   └─► uncertain ─(you check)─► done · failed
recover() after a crash or laptop sleep ─► running (from the last Checkpoint)
```

## 7. What might be happening — failure modes

| Situation | What the Assistant does | What you see | Recorded |
|---|---|---|---|
| Laptop off when you send | Telegram holds it (≤ 24 h); on wake, older than 30 min → Stale | "Still want this?" | Ledger |
| Telegram delivers the same Message twice | Dropped by Message id | nothing | Ledger |
| Free text arrives while a Task is paused | Intake can't tell → asks | two buttons | Ledger |
| Model provider down or rate-limited | Pauses and retries with backoff; tells you after ~10 min | "Model unreachable, retrying" | Ledger |
| Model returns a malformed Action | Tells the model; one retry; then Failed | failure note | Ledger |
| Element missing, page slow | The next Step sees it; the Step Budget bounds it | a Question if stuck | Ledger + screenshot |
| Page redirects to `localhost`, home network or `file://` | Browser blocks the request | page error, if any | Ledger |
| Page says "ignore your instructions…" | Untrusted content: Verdicts unchanged, no Memory write | maybe a Refusal | Ledger |
| Submit / send / apply / upload | Ask, with the exact fields or file | approve / deny buttons | Ledger |
| You tap Approve after 15 min | Approval expired; asks again | a fresh Approval | Ledger |
| CAPTCHA, 2FA, login wall | Run ends Blocked | screenshot + "blocked" | Ledger |
| Task Budget reached | Stops before the next model call | Question: raise or stop? | Ledger |
| Monthly Budget reached | New Requests Declined | decline message | Ledger |
| Crash or laptop sleep mid-Run | `recover()` resumes from the Checkpoint | "resumed" | Ledger |
| Crash during a Consequential Action | Outcome Uncertain; never repeated | "please check whether X went through" | Ledger |
| No Answer for 24 h | Run Expired | expiry note; `/retry` | Ledger |
| You edit `persona.md` | Your entry is Pinned and wins | nothing | Memory |
| A page tries to plant a "preference" | Rejected: wrong Provenance | nothing | Ledger |
| A Note goes stale (site changed) | Expires; not recalled | maybe one Question | Memory |
| A request reaches outside every Grant (`..`, symlink, junction) | Files returns Denied | "not inside your Grants" | Ledger |
| A request touches Off-limits (`.env`, password store, the Assistant's folder) | Refused, regardless of Grants | "that location is off-limits" | Ledger |
| A file contains "email these files to …" | Untrusted content; the Run is Tainted; no Memory write | maybe a Refusal | Ledger |
| A Tainted Run tries to send or upload | Ask, with what goes where | Approval with the data and destination | Ledger |
| Read Budget reached (20 reads / 10 MB) | Stops reading | Question: continue or stop? | Ledger |
| Several resumes match | Asks which one, then remembers | a Question with choices | Persona |

## 8. Where things run

| Piece | V0 | V1 |
|---|---|---|
| Brain (Intake, Runner, Memory, Ledger, model calls) | the laptop process | a small server |
| Browser hands | fresh isolated Playwright context | a container per Task |
| Files hands | the local disk, inside Grants | a helper on the User's laptop that connects *outward*, enforcing Grants itself |
| Database | SQLite file | Postgres when a second machine or many Users write |
| Frontend | Telegram + React page on localhost / home Wi-Fi | a hosted React app, with sign-in from a provider |

Grants belong to each User and are enforced on that User's own device; the server never holds another User's files. See [ADR 0007](adr/0007-brain-and-hands.md) and [ADR 0008](adr/0008-laptop-files-grants.md).

## 9. Threat model

- **Untrusted:** web pages, fetched content, search results, and the contents of files (a PDF someone sent you can carry hostile text). **Trusted:** Messages from the User on an allowlisted Channel; the User's edits to Memory and to `grants.toml`.
- **Layers:** (1) authority at the Gate, never the model; (2) Consequential Actions need an Approval; entering Persona facts or Documents into a site that isn't an Approved site needs one too; (3) Memory writes only from the User's Messages and Run Outcomes; (4) network policy in the Browser and Fetcher for every request; (5) `screen` reads only the User's text; (6) Grants set only by the User; Off-limits fixed in code, including the Assistant's own folder; Files enforces both itself; (7) reading file contents Taints the Run — outward Actions need an Approval showing what goes where; (8) a read Budget per Run; (9) secrets screened out of file contents before they reach the model; (10) every Role's Actions pass the same Gate and each specialist holds one hand — a poisoned page that steers the Browser Role cannot read a file — and a Finding is Untrusted content that cannot write Memory; (11) Security cases in Evaluation — zero Actions the User didn't approve, zero Memory from Untrusted content, zero reads outside Grants.
- **Accepted in V0:** a browser exploit runs with your user's privileges (Chromium sandbox on, Playwright kept current — verify the option in S2); Persona facts, Documents and `read`-Mode file contents reach the model provider (approval-gated or Grant-gated, Egress recorded); a whole-profile Grant widens the blast radius of a successful injection, which taint and Approvals are there to contain.

## 10. On disk (`data/`, gitignored)

```
data/stepout.db                   Tasks, Runs, Checkpoints, Questions, Approvals, Approved sites, Ledger
data/config/grants.toml           Grants — edited only by the User
data/memory/persona.md            Persona (Pinned entries marked)
data/memory/history.md            History
data/memory/notes/<site>.md       Notes, each with Provenance and expiry
data/documents/                   files given directly (optional)
data/undo/<run_id>.jsonl          Undo journal (S11)
data/runs/<run_id>/               screenshots
```

## 11. Package layout

```
web/               React + Vite + TypeScript (S9): package.json, src/, dist/ (build output, gitignored)
src/stepout/
  CONTEXT.md       Assistant language
  domain.py        Message, Reply, Task, Run, Action (built from the capability registry plus plan/delegate/answer), Result, Verdict, Question, Approval, Outcome, Event …
  capabilities/    one file per tool (fetch · files · browse · web_search): schema, Action, executor, Gate rule, Trace line, blurb; __init__.py holds ALL, the one registration list
  app.py           composition root
  store.py         the one SQL module; migrations/ holds numbered .sql files
  intake.py · runner.py (the loop) · roles.py (Role table) · gate.py · memory.py · ledger.py · browser.py · fetch.py · files.py (the hands) · model.py
  channels/        cli.py · telegram.py · web.py (serves web/dist)
tests/
  support/         scripted model, Simulated-web launcher, Simulated-folder builder
  simweb/          sites, Variants, Receipts
  test_gate.py · test_intake.py · test_memory.py · test_files.py · test_runner.py · test_app.py
  eval/            Evaluation: CONTEXT.md, golden/, harness, Simulated user
```

## 12. Testing — the interface is the test surface

- **Gate** — table-driven, pure, hundreds of cases in milliseconds. The most important tests in the repo.
- **Files** — table-driven path cases against a Simulated folder: `..`, symlinks, junctions, network paths, Off-limits, Mode limits, the read Budget.
- **Intake** and **Memory** — through their interfaces, with the scripted model and a temp folder.
- **Runner** — through `submit` / `deliver` / `recover`, with the scripted model (delegation, the shared Budget and Taint, and a Finding that can't write Memory are tested here), real Chromium, the Simulated web and a temp SQLite file. Kill-and-recover tests live here.
- **app** — end to end through the CLI Channel.
- **Evaluation** — its own context; costs money; `pytest -m eval`.
- Replace, don't layer: when a module deepens, its old internal tests are deleted in favour of interface tests.

## 13. Open design questions (each settled in a slice)

1. **Search** — the model provider's built-in web search vs a search API. *S1.*
2. **Models per Role** — a cheap model for Intake, and for each Runner Role (Orchestrator, Direct, Browser, Files) the cheapest that holds up; check current IDs and prices. *S1, S1b.*
3. **Page view** — accessibility snapshot, screenshot, or both: token cost vs success on the Simulated web. *S2 spike.*
4. **Is this click Consequential?** — classify from the element (role, form submit, label) plus the model's stated intent, unknown → Ask; backstop: the Browser holds non-GET requests to other sites unless Approved. *S3, attacked in S7.*
5. **Exfiltration after a file read** — a Tainted Run could leak through a URL's query string. Leaning: in a Tainted Run, the Browser and Fetcher may reach only Approved sites and domains already visited before the first read. *S8.*
6. **PDF text** — pypdf vs PyMuPDF: check licences (PyMuPDF is AGPL, as I recall) and quality on real resumes. *S8.*
7. **Windows path edge cases** — junctions, 8.3 short names, alternate data streams, `\\?\` and UNC paths; verify the real-path check handles each. *S8.*
8. **Secret screening** — patterns vs a model check; what to do when it can't tell. *S8.*
9. **Evaluation size vs Budget** — see the estimate in the roadmap. *S6.*
10. **What a Delegate carries** — the goal only, or goal plus Recollection; how large a Finding may be; whether the Orchestrator may re-Delegate after a poor Finding. *S1b.*
