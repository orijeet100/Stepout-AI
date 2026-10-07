# Architecture — V0

Status: draft for sign-off · Date: 2026-10-06 · Language: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md) · Requirements: [`requirements.md`](requirements.md) · Order of work: [`roadmap.md`](roadmap.md)

One Python process on the laptop. Two bounded contexts — **Assistant** (the product, `src/stepout/`) and **Evaluation** (the proof, `tests/eval/`) — see [ADR 0005](adr/0005-two-bounded-contexts.md). Design vocabulary: **module**, **interface**, **seam**, **adapter**, **depth** (leverage per unit of interface).

## 1. The shape

```
            OUTSIDE                       ASSISTANT (src/stepout)                         OUTSIDE
                                 ┌──────────────────────────────────────────────┐
 Telegram ──► Telegram adapter ─┐│                                              │
 Web page ──► Web adapter ──────┼┼─► app ──► Intake ──► Runner ──► Gate (pure) │
 Terminal ──► CLI adapter ──────┘│     ▲        │          │  ├─► Browser ──────┼──► websites
                                 │     │        │          │  ├─► Fetcher ──────┼──► websites
 EVALUATION (tests/eval)         │     │        ▼          ▼  ├─► Memory        │
 Simulated user ── Channel ──────┼─────┘      Model ◄──────┘  └─► Ledger        │
   reads Ledger ◄────────────────┼───────────────────────────────── (SQLite)    │
                                 └──────────────────────────────────┬───────────┘
                                                                    └──► model provider
```

The dependency rule: arrows point inward to `Gate` and the domain types. Nothing in the Assistant imports a Channel adapter except `app` (the composition root). Evaluation imports nothing from the Assistant except the Channel interface, the domain types and the Ledger reader.

## 2. Modules

Each is **deep**: callers learn a small interface; the behaviour behind it is large.

| Module | Interface (all a caller learns) | Hides | Depends on |
|---|---|---|---|
| **Intake** | `read(message) → Reading` | fast paths (reply-to, buttons, `/commands`), Stale check, scope screening, cheap-model routing and classification | Model, Gate.`screen`, run state, clock |
| **Runner** | `submit(task)` · `deliver(answer \| approval \| cancel)` · `recover()` | the Run state machine, Steps, the agent loop, tool dispatch, Budgets, Checkpoints, at-most-once, Recollection at start, Memory writes at end, browser lifecycle | Model, Gate, Browser, Fetcher, Memory, Ledger, clock, `notify` |
| **Gate** | `check(action, ctx) → Verdict` · `screen(request) → Screening` | every rule: Risk classes, Forbidden list, navigation rules, Approved sites, Approval matching and expiry, Budget checks | nothing — pure functions |
| **Memory** | `recall(task) → Recollection` · `remember(item) → Remembered \| Rejected` · `forget(what) → count` | Provenance check, secret/PII redaction, Pinned entries, Note expiry, bounded recall, storage format | a store behind an **internal** seam (files now; mem0 in S9) |
| **Ledger** | `record(event)` · `query(run=None, since=None) → events` | schema, append-only rule, cost totals, no Persona or Document contents | SQLite |
| **Browser** | `open() → session`; session `look() → PageView` · `do(action) → Result` · `close()` | Playwright, page views, screenshots, **network policy on every request including ones pages start themselves**, temp downloads, Chromium sandbox | Playwright |
| **Fetcher** | `get(url) → FetchedPage` | HTTP, same network policy, HTML → text, size limits | httpx |
| **app** | `main()` | wiring, the receive → read → submit/deliver loop, commands (`/status`, `/stop`, `/forget`, `/persona`, `/retry`) | everything (composition root) |

**Deletion test, applied.** Delete Gate and its rules reappear inside every tool and route — keep. Delete Ledger and every module invents its own logging and cost math — keep. A separate "router" or "scope guard" module would only pass through to the model — folded into Intake. A separate "agent loop" next to a "run manager" would force the loop to expose its state for checkpointing — folded into Runner, with the Step as an internal seam its own tests can use.

## 3. Seams and adapters

A seam is only real when two adapters exist (production + test counts).

| Seam | Adapters | Dependency kind |
|---|---|---|
| **Channel** — `messages() → stream of Message` · `send(reply)` | Telegram (S4), Web (S8), CLI (S1), Simulated user (Evaluation, S6) | external, owned translation |
| **Model** — `call(request) → response` (response carries tokens and money spent) | provider adapter (S1), scripted model (tests, S1) | true external → mocked in tests |
| **Memory store** (internal to Memory) | Markdown files (S5), mem0 (S9) | local; the rules stay above the seam |

**Deliberately not seams** (one adapter, tested with a local stand-in instead):
- **Browser** — tested with real Chromium against the Simulated web. No fake page driver: a fake drifts from real pages, and fast tests come from Gate, Intake and Memory, which need no browser.
- **Fetcher** — tested against the Simulated web.
- **Run state and Ledger storage** — SQLite in a temp file ([ADR 0006](adr/0006-sqlite-for-runs-and-ledger.md)).
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
    # Reading = NewTask(request, route) | AnswerTo(question) | ApprovalGiven(approval, yes)
    #         | Correction(task) | Command(name, args) | Declined(reason, alternative)
    #         | Stale(message) | Unclear(choices)

class Runner:
    async def submit(self, task: Task) -> None: ...
    async def deliver(self, reply: AnswerTo | ApprovalGiven | Cancel) -> None: ...
    async def recover(self) -> None: ...          # on startup

def check(action: Action, ctx: GateContext) -> Verdict: ...      # Allow | Ask(approval) | Refuse(reason)
def screen(request: str) -> Screening: ...                        # Accept | Decline(reason, alternative) | Unsure

class Memory:
    def recall(self, task: Task) -> Recollection: ...
    def remember(self, item: MemoryItem) -> Remembered | Rejected: ...
    def forget(self, what: str) -> int: ...
```

- **Intake** — Messages from anyone but the User never reach it (the adapter drops them; Intake asserts). Fast paths run before any model call: a reply to a Question is an `AnswerTo`, a button is an `ApprovalGiven`, `/x` is a `Command`. Free text while a Run is paused and unclear → `Unclear` (two buttons: "answer to the current Task" / "new Task"). `screen` runs before money is spent; the model is asked only when `screen` says `Unsure`. Error: model unreachable → the Message waits and is re-read later.
- **Runner** — one Run executes at a time; others queue. Every Action passes `check` before it happens. A Consequential Action is written as *intended* in the same transaction as the Checkpoint, then *done* after — a crash in between makes the Outcome **Uncertain**, and the Action is never repeated. Budget is checked before every model call. Recollection is taken once, at Run start; Memory is written only from the User's Answers and the Run's own Outcome. Errors: Budget reached → Question; Blocker → Blocked; malformed model output → one retry, then Failed; browser crash → resume once from the Checkpoint with a fresh browser, then Failed; no Answer for 24 h → Expired.
- **Gate** — pure and total: every Action gets a Verdict. Forbidden beats everything. Unknown Risk → Ask. An Approval matches one exact Action (same kind, target, values) and expires after ~15 min. Navigation allowed only to `http(s)` on public hosts.
- **Memory** — rejects items whose Provenance isn't a User Message or a Run Outcome. Redacts card numbers, national IDs, bank details and passwords before writing. Never overwrites a Pinned entry. Expired Notes are never recalled. Recall is bounded (the Persona plus a few Notes and History entries).
- **Ledger** — append-only. Holds references to Persona facts and Documents, never their contents. Every model call has tokens and cost.
- **Browser** — enforces the network policy on **every** request (redirects, iframes, page scripts), not only on the Assistant's own Actions, because a page can reach `localhost`, the home network or `file://` by itself. Downloads go to a temp folder.

## 5. A Message's journey

```
You: "apply to this job with my resume" ─► Telegram adapter ─► app
app ─► Intake.read ─► NewTask(route = Browse)                         [cheap model]
app ─► Runner.submit(task)
  Runner: Memory.recall ─► Recollection (Persona: name, email · Document: resume)
  each Step:
    Model.call(transcript) ─► proposes an Action                      [strong model]
    Gate.check(action)
      Allow  ─► Browser.do ─► page view ─► Checkpoint + Ledger
      Ask    ─► Approval sent with the exact fields ─► PAUSE
      Refuse ─► the model is told why; the Run continues or ends
    Model needs a phone number ─► Question sent ─► PAUSE
You: "+1 555 …" ─► Intake.read ─► AnswerTo(question) ─► Runner.deliver ─► RESUME from Checkpoint
You tap Approve ─► ApprovalGiven ─► Runner.deliver ─► Browser.do(submit)
Run ends Done ─► Memory.remember(phone, from your Answer · Note about the site) ─► result sent to you
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
| Submit / send / apply | Ask, with the exact fields | approve / deny buttons | Ledger |
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

## 8. Threat model

- **Untrusted:** web pages, fetched content, search results. **Trusted:** Messages from the User on an allowlisted Channel; the User's edits to Memory.
- **Layers:** (1) authority at the Gate, never the model; (2) Consequential Actions need an Approval; entering Persona facts or Documents into a site that isn't an Approved site needs one too; (3) Memory writes only from the User's Messages and Run Outcomes; (4) network policy in the Browser and Fetcher for every request; (5) `screen` reads only the User's text; (6) Security cases in Evaluation — zero Actions the User didn't approve, zero Memory written from Untrusted content.
- **Accepted in V0:** a browser exploit runs with your user's privileges (Chromium sandbox on, Playwright kept current — verify the option in S2); Persona facts and Documents reach the model provider when filling a form (approval-gated, Egress recorded).

## 9. On disk (`data/`, gitignored)

```
data/stepout.db                   Tasks, Runs, Checkpoints, Questions, Approvals, Approved sites, Ledger
data/memory/persona.md            Persona (Pinned entries marked)
data/memory/history.md            History
data/memory/notes/<site>.md       Notes, each with Provenance and expiry
data/documents/                   Documents (resume, …)
data/runs/<run_id>/               screenshots
```

## 10. Package layout

```
src/stepout/
  CONTEXT.md     Assistant language
  domain.py      Message, Reply, Task, Run, Action, Verdict, Question, Approval, Outcome, Event …
  app.py         composition root
  intake.py · runner.py · gate.py · memory.py · ledger.py · browser.py · fetch.py · model.py
  channels/      cli.py · telegram.py · web.py
tests/
  support/       scripted model, Simulated-web launcher
  simweb/        sites, Variants, Receipts
  test_gate.py · test_intake.py · test_memory.py · test_runner.py · test_app.py
  eval/          Evaluation: CONTEXT.md, golden/, harness, Simulated user
```

## 11. Testing — the interface is the test surface

- **Gate** — table-driven, pure, hundreds of cases in milliseconds. The most important tests in the repo.
- **Intake** and **Memory** — through their interfaces, with the scripted model and a temp folder.
- **Runner** — through `submit` / `deliver` / `recover`, with the scripted model, real Chromium, the Simulated web and a temp SQLite file. Kill-and-recover tests live here.
- **app** — end to end through the CLI Channel.
- **Evaluation** — its own context; costs money; `pytest -m eval`.
- Replace, don't layer: when a module deepens, its old internal tests are deleted in favour of interface tests.

## 12. Open design questions (each settled in a slice)

1. **Search** — the model provider's built-in web search vs a search API. *S1.*
2. **Page view** — accessibility snapshot, screenshot, or both: token cost vs success on the Simulated web. *S2 spike.*
3. **Is this click Consequential?** — classify from the element (role, form submit, label) plus the model's stated intent, unknown → Ask; backstop: the Browser holds non-GET requests to other sites unless Approved. *S3, attacked in S7.*
4. **Models per role** — a cheap model for Intake, a strong one for the Runner; check current IDs and prices. *S1.*
5. **Evaluation size vs Budget** — see the estimate in the roadmap. *S6.*
