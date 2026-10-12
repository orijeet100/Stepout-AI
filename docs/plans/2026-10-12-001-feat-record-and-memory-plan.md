---
title: "feat: Memory on Mem0, a managed Record, and one retry policy"
type: feat
status: active
date: 2026-10-12
origin: docs/brainstorms/2026-10-11-record-and-memory-requirements.md
---

# feat: Memory on Mem0, a managed Record, and one retry policy

## Overview

Iteration 2 makes four changes to a working V0, in this order:

1. The **Record** becomes complete and trustworthy: a log file, tokens and durations on every step, every attempt recorded, no Run left "running".
2. Model calls get **one written retry policy** at the Model port, replacing today's implicit, per-adapter behaviour.
3. **Chats become manageable** (rename, search, delete-with-purge, export) with retention and a monthly cap.
4. **Memory** arrives behind the existing seam: a Persona file, History written by code, and learned facts in Mem0, with a plain-file baseline for measured comparison.

Measurement fields land first, because Memory's value cannot be shown without them (see origin: Key Decisions).

## Problem Frame

V0 starts every chat from zero, cannot be diagnosed after the terminal closes, cannot manage or delete its history, records cost but not tokens, time or attempts, and relies on whatever retries its provider SDK happens to do. See the origin document's Problem Frame. This plan delivers its requirements R1 to R26 and N1 to N11 without changing the Gate, Taint or the read-only rules.

## Requirements Trace

| Requirement | Delivered by |
|---|---|
| R1 Persona file, Pinned | U7 |
| R2 Mem0 for the learned layer, file baseline, one switch | U7, U9 |
| R3 What Mem0 may be fed: user messages only; History by code, verbatim | U7, U8, U9 |
| R4 Writes are visible (Trace, `/memory`) | U7, U8 |
| R5 `/remember`, `/memory`, `/forget` in both channels | U7 |
| R6 Recollection, bounded, fail-open | U7 |
| R7 Memory is data, not authority | U7 |
| R8 Thin entries from Tainted Runs | U7 |
| R9 Memory off | U7 |
| R10 Mem0 local, telemetry off | U9 |
| R11 Mem0's model calls metered | U8, U9 |
| R12 Rename, delete, search, export | U5 |
| R13 Delete means delete | U5 |
| R14 No Run left running | U4 |
| R15 App log | U1 |
| R16 Retention | U6, U10 |
| R17 Monthly cap | U6 |
| R18 Every step described (tokens, time, attempts), no contents | U2, U4 |
| R19 Handoffs recorded as ids and sizes | U4, U7 |
| R20 Capture, off by default | U10 |
| R21 One owner for retries | U2 |
| R22 Classified policy table | U2, U3 |
| R23 Bounded | U2 |
| R24 Visible | U2, U4, U11 |
| R25 Proved offline | U2, U3 |
| R26 Memory view in the page | U11 |
| N1 to N11 | see System-Wide Impact and the units' verification |

## Scope Boundaries

Carried from the origin document:

- No Notes (Assistant-written, expiring site know-how), no hosted Mem0, no graph memory, no Mem0 fed from replies or tool output.
- No Questions, Approvals or pause/resume (roadmap item 2 is next).
- No Telegram, multi-user, cloud backup, encryption at rest or external observability service.
- No Pydantic AI parity run or `AnthropicModel` removal here; the retry policy is written once at the Model port so it does not wait for that.
- No automatic whole-Run retry and no circuit breaker.

Added by planning:

- Browser navigation retries are out: a page's state makes a repeat less clearly safe and the Trace's shot sequence would need rework. The Fetcher is the only tool with retries.
- Chat search is a substring scan, not full-text indexing, until measured slow.

## Context & Research

### Relevant Code and Patterns

- `src/stepout/model.py`: `Model` protocol, `AnthropicModel`, `_explain` (maps SDK errors to `Failure`), `ModelResponse`, `call_to_action`. The client is a bare `anthropic.AsyncAnthropic()`, so SDK default retries apply silently.
- `src/stepout/pydantic_model.py`: `PydanticModel`, its own `_explain`; it calls `direct.model_request` and adds no retry layer of its own.
- `src/stepout/failure.py`: `Failure(kind, message, status)`; `UNEXPECTED` says "details are in the terminal".
- `src/stepout/runner.py`: `submit`, `_agent`, `_unless_stopped` (Stop cancels the awaited call, including any sleep), `_emit` (Ledger then Trace), `_delta(reset=True)` (the page already knows how to discard streamed words), `charge`.
- `src/stepout/screening.py` and `src/stepout/search.py`: single model calls outside the loop; Screening already uses a one-off tool (`tool_defs`, `ToolCall`), the pattern the Extractor follows.
- `src/stepout/intake.py` and `src/stepout/app.py`: `CommandReading` is produced for any `/word` but `app.run` answers "Unknown command" to all of them, so no command exists yet.
- `src/stepout/ledger.py`, `src/stepout/store.py`, `src/stepout/migrations/0001..0006`: additive migrations by `PRAGMA user_version`; `end_run(run_id, outcome, cost, tainted)`; chat messages are `events` rows with `kind='message'`.
- `src/stepout/history.py`: `_did` builds the one-line "what was done" from step events (reused for History entries); `list_conversations` is N+1.
- `src/stepout/channels/web.py`: `HistoryReader` protocol and `StoreHistory`, the routes table (`GET/POST /api/conversations`, `GET /api/conversations/{id}`, `/api/runs/{run}/events`, `/shots`).
- `src/stepout/redact.py`: `redact(text) -> (text, count)`, reusable for Capture.
- `src/stepout/capabilities/fetch.py`: catches `BlockedUrl` and `httpx.HTTPError` and returns text; the place for tool retries.
- `tests/support/scripted_model.py`, `tests/test_model.py` (`FakeMessages`), `tests/support/acceptance_offline.py`, `scripts/acceptance.py`: the offline patterns to extend.

### Institutional Learnings

- `docs/solutions/` does not exist; the project's learnings live in `docs/history.md` and `docs/adr/`.
- ADR 0013: a streaming check passed on frames and failed in the real page. Page-facing units here are verified in the real browser.
- ADR 0003 designed `recall` / `remember` / `forget` over a storage seam with mem0 as a measured challenger; this plan builds exactly that seam with two adapters.
- ADR 0012: Screening carries a paid, labelled eval, so its prompt is not changed for a side benefit.

### External References

- Mem0 open source (checked 2026-10-12): `mem0ai` 2.2.1 resolves cleanly in this venv (a dependency dry-run adds `qdrant-client`, `numpy`, `grpcio`, `posthog`, `SQLAlchemy`, `pytz`, `pywin32`; nothing conflicts with Pydantic 2.13, Pydantic AI 2.55, anthropic 1.13, openai 3.29).
  - `add(..., infer=False)` stores raw text with no LLM call; `infer=True` makes one LLM call and, on v3, returns only ADD events (additive).
  - `AsyncMemory` has `add`, `search`, `get_all`, `get`, `update`, `delete`, `delete_all`; results are `{"results": [{id, memory, score, metadata}]}`.
  - Anonymous telemetry is on by default; `MEM0_TELEMETRY=False` disables it.
  - Local Qdrant's `path` defaults to `/tmp/qdrant`; `embedding_model_dims` (1536 for `text-embedding-3-small`) and `history_db_path` are configurable.
  - Anthropic has no embedder; the OpenAI embedder is the chosen one (see origin: Key Decisions).
  - Doc pages disagree on whether `search` takes `user_id=` or `filters=`; the pinned version decides (deferred below).
- Pydantic AI docs: nothing retries at the transport layer unless a retrying transport is installed; `ModelHTTPError.retry_after` gives the parsed `Retry-After` seconds; `InstrumentationSettings(include_content=False)` exists for later telemetry.

## Key Technical Decisions

- **Retries live in one `RetryingModel` wrapper at the Model port, fed by a per-Run scope carried in a context variable.** The `Model` protocol and every fake stay unchanged; Screening, the Searcher and the Runner all get the same policy; the Runner gives the scope its `emit` and a `reset_stream`. Alternatives: a retry loop in the Runner (Screening and the Searcher would need a second copy) or inside each adapter (two copies, drift).
- **SDK-level retries are switched off in both adapters**, so every attempt is ours, recorded and bounded. If a provider's SDK cannot be switched off, that is written down as a ceiling and the policy's attempt count is lowered to compensate (verified by counting HTTP requests per attempt).
- **Mem0 is the store, the embedder and the search; extraction runs through our Model port.** An `Extractor` on the Screening pattern asks the cheap tier for facts from the User's message and Mem0 stores them with `infer=False`. This keeps R11 true by construction (metered, retried, Stop-aware, in the Ledger, testable offline with the scripted model), keeps Mem0's own LLM unused, and loses little because Mem0's current `add` is additive. This is a deliberate deviation from "Mem0 does the extracting" and is flagged in the hand-off.
- **Extraction is its own call, not folded into Screening.** Screening is a safety gate with a labelled paid eval; adding an output field risks its accuracy to save about a tenth of a cent.
- **Persona stays a Markdown file outside Mem0.** One bullet per entry; the entry id is a short hash of the line, so editing other lines does not renumber. `/remember` appends, `/forget` removes that one line, nothing else touches the file.
- **History is written by code from the Run's events** with the shared `did` function, after the reply is sent, inline and bounded (5 s). A Tainted Run writes request and outcome only.
- **Recollection is assembled by code with one search call and a hard 3 s limit.** Any failure or timeout gives Persona only, with a Trace line. Memory never blocks or fails a Run.
- **Measurement fields live in each event's `data`; totals live in `runs` columns** (tokens, retries, retry wait) so per-Run questions are one query and no per-event schema change is needed.
- **Chat search is a substring scan** (about 2,000 message rows after a year). A `ponytail:` comment names the ceiling; full-text indexing arrives only if measured slow.
- **Delete is a purge**: one database transaction for the chat's events, Runs and Tasks, then best-effort removal of screenshots and Capture files, then History entries by chat. It is refused (409) while the chat has a live or queued Run. The glossary's "append-only" is amended: the Assistant never edits the Ledger; the User may purge.
- **Interrupted Runs are closed at startup**, assuming one process per data folder (a ceiling, noted).
- **The Log is standard-library `logging`**, JSON lines, rotating. Exception messages are not written for exception types that echo input (Pydantic validation errors); type and frames are.
- **Capture is opt-in**, refused for any Run that has read a file, passed through `redact`, and removed with its chat or by age.
- **No exporter to Langfuse or OpenTelemetry now.** Events already carry `run_id` and `parent`, so a later exporter is a mapping, not a rewrite.
- **Memory defaults to Mem0 when `OPENAI_API_KEY` is present and to the file baseline otherwise**, with a start-up note either way. `STEPOUT_MEMORY=off|files|mem0` overrides.
- **Monthly cap default $10** (an assumption; `STEPOUT_MONTH_CAP_USD`), and a Run's cap becomes the lesser of the per-Run cap and what the month has left.

## Alternative Approaches Considered

- **Memory as plain files only, Mem0 later (ADR 0003 as written):** simplest and fully owned, but the User chose Mem0 now; the file baseline is kept so the comparison ADR 0003 asked for still happens.
- **Mem0 doing its own extraction (`infer=True`):** closer to "using Mem0 fully", but its model calls would bypass the Ledger, the cap, Stop and the retry policy, and tests would need a fake Mem0 LLM. Rejected for R11.
- **Folding extraction into the Screening call:** saves a call per message but puts Screening's paid eval at risk. Rejected.
- **Chat persistence on Postgres, Redis or a hosted store:** nothing here needs a second machine ([ADR 0006](../adr/0006-sqlite-for-runs-and-ledger.md)). SQLite with additive migrations stays.
- **Langfuse, OpenTelemetry or Logfire for steps:** hosted options send prompts off the laptop and self-hosted ones are multi-service stacks for one user. Ledger events already map one-to-one onto spans for a later exporter.
- **A retry loop per call site, or inside each adapter:** three or two copies of a policy that must stay identical.

## Success Metrics

From the origin document, verified in Unit 12:

- Memory-on takes fewer Actions or less money than Memory-off on the Persona-sensitive "second chat" tasks without regressing the rest, for both adapters, in one table.
- The planted-injection query still passes and no Memory write comes from Untrusted content.
- `/memory` answers "what does it know about me?" and `/forget` removes any item.
- A killed process leaves no Run showing as running and the log explains the failure.
- Every retry row has an offline test; no Run exceeds its cap because of retries.
- A Run can be reconstructed from the Ledger alone, without file contents.

## Open Questions

### Resolved During Planning

- Persona file format and editing: Markdown bullets, hashed ids, append and remove-one only.
- History as file or view: both adapters write entries by code; the baseline is a file the User can open, Mem0 holds the primary copy with the same text.
- Tokens and durations: in event `data`, with totals on `runs`.
- Search method: substring scan.
- Where extraction happens and when memory is written: separate call, after the reply, inline, 5 s limit.
- Redacting the log and Capture: `redact.redact` for Capture; the Log avoids content by construction (ids, kinds, sizes) plus the exception-message rule.
- Default memory mode: Mem0 if the key is present, else files.

### Deferred to Implementation

- Mem0 2.2.1's exact `search` / `get_all` / `delete` signatures and metadata filtering (docs show both `user_id=` and `filters=`); read the pinned package source first.
- Whether Mem0 writes anything under the home folder (`MEM0_DIR`) and how to redirect it into `data/memory/`.
- Local Qdrant's practical size limit and Windows file locking; the app must close the store cleanly.
- How to fake embeddings in tests (a deterministic stub with a small `embedding_model_dims` is the intent).
- How to switch off SDK retries for each Pydantic AI provider path, proved by counting requests.
- What a provider bills for a stream that was cut; the estimate rule for a failed attempt that had begun streaming.
- Relevance score scale and threshold, and the Recollection budget (starting point: about 2,000 characters in total).
- Retry numbers (3 attempts, about 1 to 8 s, 30 s `Retry-After` ceiling, 60 s and 8 retries per Run) are starting values; calibrate with the fault tests and the first live run.
- The month's spend: which SUM equals what was actually billed (Run totals plus standalone screening and memory events); check against a known Run.
- Persona truncation when the file is larger than its budget.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

One message, with Memory and retries in place:

```mermaid
sequenceDiagram
    participant U as User
    participant A as app.run
    participant I as Intake + Screening
    participant R as Runner
    participant M as Memory (Persona + store)
    participant P as RetryingModel (Model port)
    participant L as Ledger + Log

    U->>A: message
    A->>A: month cap check (refuse with a line at the cap)
    A->>I: read(message)
    I->>P: screen (same retry policy, no Run scope yet)
    A->>R: submit(task)
    R->>M: recall(request), 3 s limit, fail-open
    M-->>R: Recollection (ids, size) or none
    R->>L: memory event (op=recall)
    loop each agent step
        R->>P: call(request)
        P->>P: classify, back off, record each attempt
        P-->>L: retry events (attempt, cause, wait)
        P-->>R: response (tokens, duration, attempts)
        R->>L: step, result events (no contents)
    end
    R-->>U: reply (saved, then sent)
    R->>M: record_run(entry) (code-written; thin if Tainted)
    A->>P: extract facts from the User's message only
    A->>M: learn(facts) (infer=False)
    M-->>L: memory events (op=write, cost, source message)
```

The retry table (origin R22) is the policy; the wrapper only looks a `Failure.kind` up in it, so adding or tuning a row is a data change.

## Implementation Units

### Phase 1: A Record you can trust

- [ ] **Unit 1: Run scope and the app log**

**Goal:** Every log line and failure outside the terminal carries chat and run ids, in a rotating file, and the per-Run scope that later units use exists.

**Requirements:** R15, N5, N9

**Dependencies:** None

**Files:**
- Create: `src/stepout/scope.py` (the per-Run scope and its context variable)
- Create: `src/stepout/logs.py` (file handler, JSON-lines format, id filter)
- Modify: `src/stepout/runner.py` (set and reset the scope in `submit`)
- Modify: `src/stepout/app.py` (configure logging first; log the start-up configuration)
- Modify: `src/stepout/failure.py` (`UNEXPECTED` points to the log file)
- Modify: `.env.example` (document `STEPOUT_LOG_LEVEL`)
- Test: `tests/test_logs.py`

**Approach:**
- The scope carries `run_id`, `task_id`, `conversation_id`, the Runner's `emit` and a `reset_stream` callable, plus counters later units fill. It is optional everywhere: no scope means a call outside a Run (Screening).
- The log file lives under `data/logs/`, rotates by size, level from `STEPOUT_LOG_LEVEL`.
- Existing `logging.exception(...)` call sites keep working and gain ids.
- Never write contents: messages are ids, kinds and sizes. For exceptions, write the type and frames but not the message for types that echo their input (Pydantic validation errors, JSON decode errors).

**Patterns to follow:**
- `app.web_port` for the environment-variable idiom; `logging.getLogger(__name__)` as in `src/stepout/browser.py` and `src/stepout/runner.py`.

**Test scenarios:**
- A line logged inside a Run carries that Run's and chat's ids; one logged outside carries neither and does not fail.
- A Run that fails with an exception whose message contains a planted secret leaves the log without it (type and frames only).
- Rotation keeps a bounded number of files; the level variable changes what is written.
- Configuring twice does not duplicate handlers.

**Verification:**
- A forced failure outside a Run (a trace frame that cannot be sent) appears in the log file with its ids after the terminal is gone.

- [ ] **Unit 2: One retry policy at the Model port**

**Goal:** Every model call (Runner, Screening, Searcher, later the Extractor) follows one written, bounded, recorded policy on both adapters.

**Requirements:** R21, R22 (model rows), R23, R24, R25, R18 (attempts, duration, tokens), N5

**Dependencies:** Unit 1

**Execution note:** Test-first: build the fault-injecting model double and the table-driven tests, then the wrapper.

**Files:**
- Create: `src/stepout/retry.py` (policy as data, classification, backoff, the `RetryingModel` wrapper)
- Create: `tests/support/faulty_model.py` (scripted outcomes: a Failure with status and `retry_after`, a response, a stream cut after N words)
- Create: `docs/adr/0015-one-retry-policy-at-the-model-port.md`
- Modify: `src/stepout/failure.py` (`retry_after`, short `detail`)
- Modify: `src/stepout/model.py` (client with SDK retries off; `retry_after` and `detail` in `_explain`; tokens on `ModelResponse`; `attempts`, `duration_ms`)
- Modify: `src/stepout/pydantic_model.py` (SDK retries off per provider; `retry_after` from `ModelHTTPError`; tokens)
- Modify: `src/stepout/app.py` and `scripts/acceptance.py` (wrap the model once)
- Modify: `src/stepout/runner.py` (give the scope its `emit` and `reset_stream`; keep per-Run retry counters)
- Modify: `docs/adr/README.md`
- Test: `tests/test_retry.py`, `tests/test_model.py`, `tests/test_pydantic_model.py`

**Approach:**
- The wrapper implements the `Model` protocol, passes through `streams`, `target` and `key_vars`, tracks whether any words were delivered to `on_text`, and consults the policy table by `Failure.kind`.
- Per attempt it records a `retry` event through the scope (attempt, cause, status, wait, cost) and a log line; with no scope it only logs.
- A failure after words reached the page triggers `reset_stream` once and allows one more attempt, never a silent duplicate.
- A `Retry-After` above the ceiling fails fast with a line that names the wait.
- Per-Run bounds (8 retries, 60 s total wait) and the cap are checked before each wait. Stop is not handled here: the Runner's `_unless_stopped` already cancels the awaited call, which ends the sleep.
- The sleep and the jitter source are injectable so tests use a fake clock.
- A failed attempt that had begun streaming is charged an estimate from the request's size; one that never connected costs nothing.

**Patterns to follow:**
- `tests/test_model.py` `FakeMessages`; `tests/support/scripted_model.py`; the shared helpers already used by both adapters (`call_to_action`, `client_tools`).

**Test scenarios:**
- 429 with `Retry-After: 2`: waits 2 s, then succeeds; one `retry` event with cause `rate_limit`.
- 429 with `Retry-After: 120`: no wait, fails fast with a line naming the wait.
- 529 twice then success: three attempts, two retry events, `attempts == 3`.
- 529 three times: ends with the overloaded line after exactly three attempts.
- Connection reset before any byte: retried; stream cut after words: `reset_stream` once, then success or failure, at most two attempts.
- 400, 401, 402, no key, no price: exactly one attempt.
- Nine transient failures spread over several calls of one Run: the ninth is not retried; total wait never exceeds 60 s.
- Spend at the cap: no retry is started.
- Stop during a backoff: the call is cancelled, no further attempt, no event after the cancel.
- Both real adapters, driven with a fake transport that returns 529: exactly one HTTP request per attempt (proves the SDK layer is off).
- Without a scope (Screening): same attempts, no events, a log line.

**Verification:**
- Every row of the origin's retry table has a passing offline test, deterministic under the fake clock.
- A fault run of the offline acceptance harness completes with attempts visible in the Ledger.

- [ ] **Unit 3: Repair for a malformed reply, and retries for the Fetcher**

**Goal:** The two remaining retry rows: one repair for a malformed or invalid tool call, and bounded retries for read-only fetches.

**Requirements:** R22 (malformed and read-only tool rows), R24, R25

**Dependencies:** Unit 2

**Files:**
- Modify: `src/stepout/retry.py` (repair path: one re-ask per call, three per Run)
- Modify: `src/stepout/model.py` and `src/stepout/pydantic_model.py` (a `detail` that names the field and rule, never the value)
- Modify: `src/stepout/capabilities/fetch.py` (retry transient errors, emit `retry` events)
- Test: `tests/test_retry.py`, `tests/test_fetch.py`, `tests/test_capabilities.py`

**Approach:**
- The repair appends a short, value-free error to the request ("your last call was missing field X") and calls again once; a second failure is the existing "could not be understood" line.
- The Fetcher retries timeouts, connection errors, 5xx and 429 (with `Retry-After`) up to two attempts; `BlockedUrl`, other 4xx and policy refusals are never retried. A retry is an event under the step, so the Trace shows it.

**Patterns to follow:**
- `Capability.run` and `ctx.emit` in `src/stepout/capabilities/base.py`; the local-server style in `tests/test_fetch.py`.

**Test scenarios:**
- A reply missing a required field is repaired on the second call and the Run continues; two bad replies in a row fail with the existing line.
- The repair text contains no part of the model's earlier output values.
- Three malformed replies in one Run: the fourth is not repaired.
- Fetch: a 503 then 200 returns the page with one retry event; a 404 is one attempt; a blocked address is one attempt; a repeated identical fetch still hits the existing repeat guard.

**Verification:**
- The offline acceptance harness still passes, and a planted malformed reply no longer fails its Run.

- [ ] **Unit 4: Steps with tokens and time, handoffs, and no Run left running**

**Goal:** A Run can be reconstructed step by step from the Ledger alone, without file contents, and a crash leaves no Run open.

**Requirements:** R14, R18, R19, R24, N8

**Dependencies:** Unit 2

**Files:**
- Create: `src/stepout/migrations/0007_run_totals.sql` (tokens, retries and wait on `runs`)
- Modify: `src/stepout/runner.py` (step data: model, tokens, duration, attempts, prompt size; a `result` event after each tool; `finding_chars` on `return`; run totals)
- Modify: `src/stepout/ledger.py` (`end_run` takes the totals as keywords with defaults; `close_interrupted`)
- Modify: `src/stepout/store.py` (copy the database file before a migration that changes the schema)
- Modify: `src/stepout/domain.py` (`Outcome.INTERRUPTED`; the `Event.kind` comment)
- Modify: `src/stepout/history.py` (an interrupted Run reads as failed; `did` takes events so Memory can reuse it)
- Modify: `src/stepout/app.py` (close interrupted Runs before the channel starts)
- Modify: `src/stepout/contract.py` and `docs/ui-contract.md` (additive: step fields, `result` and `retry` kinds, run totals)
- Test: `tests/test_runs.py`, `tests/test_ledger.py`, `tests/test_runner.py`, `tests/test_contract.py`, `tests/test_taint.py`

**Approach:**
- New data rides in each event's `data`; the `runs` columns hold totals for cheap per-Run queries.
- `result` events record duration, size and truncation, never text.
- `close_interrupted` marks Runs with no `ended_at` as `interrupted` with a plain line, once, at start, assuming one process per data folder.
- `end_run` keeps its current positional signature working so existing tests and callers do not change.
- Backup before migration (N8): the Store copies the database file before applying a migration, as the hand-made `.bak-before-v5` and `-v6` were.

**Patterns to follow:**
- Migration style in `src/stepout/migrations/0004_runs.sql`; `Event` and `_emit` in `runner.py`.

**Test scenarios:**
- A Run's `step` events carry model, input and output tokens, duration, attempts and prompt size; a tool call is followed by a `result` event under its step.
- No event data of a Run that read a file contains the planted file text (tokens, sizes and paths only).
- Run totals equal the sum of its events.
- A Run left open is closed as `interrupted` at the next start; finished Runs and other chats are untouched; the chat view shows it as failed.
- An old database opens and migrates; the backup rule (below) leaves a copy.

**Verification:**
- Replaying `run_events` for a finished Run lists every Role, action, verdict, token count and duration in order.

### Phase 2: Chats you can manage

- [ ] **Unit 5: Rename, search, delete with purge, export**

**Goal:** The User can rename, find, delete and export chats; delete removes everything about the chat.

**Requirements:** R12, R13, N7

**Dependencies:** Unit 4

**Files:**
- Modify: `src/stepout/ledger.py` (`rename_conversation`, `delete_conversation` returning the Run ids)
- Modify: `src/stepout/history.py` (search; fix the per-chat query pattern in `list_conversations`; export to Markdown)
- Modify: `src/stepout/channels/web.py` (`PATCH` and `DELETE /api/conversations/{id}`, `?q=` on the list, `GET /api/conversations/{id}/export`; `409` while the chat has a live or queued Run)
- Modify: `src/stepout/app.py` (a small keeper that deletes screenshots and later Capture files and History entries)
- Modify: `src/stepout/contract.py`, `docs/ui-contract.md`
- Modify: `src/stepout/CONTEXT.md` (Ledger: "append-only" amended; Forget versus delete)
- Test: `tests/test_ledger.py`, `tests/test_history.py`, `tests/test_web_channel.py`

**Approach:**
- The purge is one transaction over events, runs and tasks for the chat, then best-effort file removal with a log line on failure.
- The confirmation lives in the page; the API refuses a live chat.
- Search reads message text only (never trace data) and returns chat summaries.

**Patterns to follow:**
- `StoreHistory` and `HistoryReader` in `src/stepout/channels/web.py`; `_valid_id` for path ids.

**Test scenarios:**
- Delete removes messages, events, Runs, Tasks and screenshots of that chat and nothing of another chat.
- Delete of a chat with a live or queued Run answers `409` and changes nothing.
- Rename persists and shows in the list; search finds a message in an old chat and ignores trace text.
- Export contains the messages in order and no trace data.

**Verification:**
- In the real page, deleting a chat removes it from the list and its screenshots return 404.

- [ ] **Unit 6: Retention sweeps and the monthly cap**

**Goal:** Screenshots and Capture files do not grow forever, and a month's spend has a ceiling.

**Requirements:** R16, R17, N3

**Dependencies:** Unit 4

**Files:**
- Create: `src/stepout/housekeeping.py` (age sweep for `data/runs` and `data/capture`)
- Modify: `src/stepout/ledger.py` (`month_spend`)
- Modify: `src/stepout/app.py` (run the sweep at start; refuse a message at the cap with a plain line, slash commands still allowed)
- Modify: `src/stepout/runner.py` (a Run's cap is the lesser of the per-Run cap and the month's remainder)
- Modify: `.env.example`, `CLAUDE.md` (document `STEPOUT_MONTH_CAP_USD`)
- Test: `tests/test_housekeeping.py`, `tests/test_ledger.py`, `tests/test_app.py`

**Approach:**
- Age sweep by modification time, default 30 days (a starting value).
- The month's spend is the sum of what was actually charged: Run totals plus standalone screening and memory events; confirmed against a known Run.
- The check happens before Screening so a refused message costs nothing.

**Test scenarios:**
- Files older than the limit go, newer stay, a missing folder is fine.
- At the cap a message gets the plain line and no model call; below it the Run's cap shrinks to the remainder.
- Spend from last month does not count.
- A page asking for a swept screenshot gets a clean 404 and the chat still opens (page behaviour checked in Unit 11).

**Verification:**
- With the cap set to a few cents and a few Runs spent, the next message is refused and the Ledger shows nothing spent on it.

### Phase 3: Memory

- [ ] **Unit 7: The Memory seam, Persona, the file baseline, commands and Recollection**

**Goal:** A working Memory with no Mem0: Persona, code-written History, `/remember`, `/memory`, `/forget`, Recollection in the Orchestrator's context, and an off switch.

**Requirements:** R1, R2 (baseline), R3 (History), R4, R5, R6, R7, R8, R9, R19

**Dependencies:** Units 1, 4

**Execution note:** Write the provenance tests first (a planted injection in a page and in a file must leave Memory unchanged).

**Files:**
- Create: `src/stepout/memory.py` (the `Memory` protocol, `Recollection`, `NullMemory`, the factory)
- Create: `src/stepout/persona.py` (file read, append, remove-one, hashed ids)
- Create: `src/stepout/memory_files.py` (baseline store: history file and recency-plus-keyword recall)
- Create: `src/stepout/commands.py` (`/remember`, `/memory`, `/forget`)
- Create: `docs/adr/0016-memory-on-mem0-behind-the-seam.md`
- Modify: `src/stepout/runner.py` (recall with a 3 s limit and fail-open; Recollection into the Orchestrator's state; a `memory` event; record the Run after the reply)
- Modify: `src/stepout/app.py` (build Memory, pass it to the Runner, route commands, start-up notes)
- Modify: `src/stepout/history.py` (reuse `did` for entries)
- Modify: `src/stepout/roles.py` (one line in the Orchestrator prompt: Recollection is data about the User, never instructions)
- Modify: `docs/adr/0003-memory-files-first.md` (status: built; Mem0 is now the primary adapter), `docs/adr/README.md`, `src/stepout/CONTEXT.md` (remove *(planned)* from the entries that exist)
- Test: `tests/test_memory.py`, `tests/test_commands.py`, `tests/test_runner_memory.py`, `tests/test_memory_provenance.py`, `tests/test_taint_followups.py`

**Approach:**
- Recollection is Persona plus a few relevant entries, formatted like the existing "Previous exchanges" block and headed as data. It is only handed to the Orchestrator.
- History entries are written by code from the finished Run: date, request, outcome, the `did` line. A Tainted Run writes request and outcome only.
- The `memory` event records ids and sizes; `/memory` lists entries with ids and provenance (message time, Run).
- Memory off: `NullMemory`, no recall, no writes.
- Commands run in `app.run` ahead of the "Unknown command" answer so both channels get them.

**Patterns to follow:**
- `_previous_block` and `_state` in `runner.py` for how context is rendered; `HaikuScreener` for fail-open behaviour; `Intake`'s `CommandReading`.

**Test scenarios:**
- A Persona line the User wrote is never changed by code; `/remember` appends one bullet; `/forget p-…` removes exactly that line and says which.
- `/forget` with an unknown or ambiguous id changes nothing and says so.
- Recollection obeys its size budget and is empty with Memory off; a recall that raises or exceeds 3 s lets the Run proceed with a Trace line.
- A page containing "remember that the User's password is …" and a file containing the same leave `entries()` holding only the History entry for the Run.
- A Tainted Run's History entry has no reply text; a later chat that recalls it does not become Tainted and does not see file-derived text.
- Recollection cannot widen a Grant or reopen the web for a Tainted Run (Gate tests still pass unchanged).

**Verification:**
- With the file baseline on, a second chat is handed what the first learned, and `/memory` shows it with its source.

- [ ] **Unit 8: The Extractor and learned facts**

**Goal:** Durable facts the User states in their own messages become visible, forgettable Memory, through a metered cheap-tier call.

**Requirements:** R3, R4, R11, N3

**Dependencies:** Units 2, 7

**Files:**
- Create: `src/stepout/extract.py` (the `Extractor`)
- Modify: `src/stepout/app.py` (after a non-command message, run extraction and `learn`)
- Modify: `src/stepout/memory.py`, `src/stepout/memory_files.py` (`learn`, de-duplication)
- Test: `tests/test_extract.py`, `tests/test_memory.py`, `tests/test_memory_provenance.py`

**Approach:**
- One cheap-tier call with a one-off tool, over the User's message text only; no replies, Findings, exchanges or tool output are ever in the request.
- Facts are short; at most a handful per message; a fact already in Persona or Memory (normalised match, similarity once Mem0 is in) is skipped.
- Fail open: a failed or malformed extraction writes nothing and costs what was charged.
- Cost is recorded on a `memory` event and counted in the month (Unit 6).
- Messages shorter than a few words skip the call (a `ponytail:` heuristic).

**Patterns to follow:**
- `screening.py` (`_SCREEN_TOOL`, `ToolCall`, `_decision`, fail-open in `Intake.read`).

**Test scenarios:**
- The request sent to the model contains the User's message and nothing else (asserted on `ScriptedModel.requests`).
- A stated fact becomes an entry with its source message id; the same fact twice is stored once.
- A malformed or empty tool call writes nothing and does not fail the message.
- Extraction cost appears on the `memory` event; Memory off makes no call.
- A message pasted with web text that contains instructions yields facts or nothing, never an action.

**Verification:**
- Saying "my resume is in D:\Career" in one chat and asking for it in another reaches the Finder with the folder, with the write visible in `/memory`.

- [ ] **Unit 9: The Mem0 store**

**Goal:** Mem0 is the primary Memory adapter, local, with telemetry off, behind the same seam as the file baseline.

**Requirements:** R2, R10, R11, N1, N4, N10, N11

**Dependencies:** Units 7, 8

**Files:**
- Create: `src/stepout/memory_mem0.py` (adapter over `AsyncMemory`; embedding cost estimate)
- Modify: `pyproject.toml` (`mem0ai==2.2.1`, pinned exactly)
- Modify: `src/stepout/memory.py` (factory: `STEPOUT_MEMORY`, key check, fallback with a note)
- Modify: `src/stepout/app.py` (`startup_notes`: `OPENAI_API_KEY` when Mem0 is selected)
- Modify: `.env.example`, `CLAUDE.md` (key, switch, reinstall note after pulling `pyproject.toml`)
- Test: `tests/test_memory_mem0.py`, `tests/test_live_memory.py` (marked `eval`)

**Approach:**
- Telemetry is disabled before the package is imported; its vector store, collection and history database sit under `data/memory/`; embedding dimensions match the embedder.
- Every write is `infer=False`. Entries carry metadata: kind (fact or history), conversation, Run, source message, time.
- Recall is one `search` bounded by the Recollection limit; entries and forgets use `get_all` and `delete`; forget-by-chat filters on stored metadata.
- Embedding cost is estimated from text size at the published price and recorded (an estimate, labelled as one).
- The adapter closes cleanly; the store is single-process.
- Mem0's internal OpenAI client keeps its own retries; this is a documented ceiling, not part of R21.
- If the key is missing or the store fails to open, the factory falls back to the file baseline and says so at start.

**Patterns to follow:**
- `memory_files.py` for the shape of the adapter; `pydantic_model.PydanticModel.key_vars` for the key checks.

**Test scenarios:**
- Against a temp folder with a deterministic fake embedder: add, search ordering, forget by id, forget by chat, entries listing.
- Mem0's own LLM is never invoked (a stub that raises if called).
- Telemetry is off and no file is written outside `data/memory/`.
- Missing key: the factory returns the file baseline and a start-up note.
- A search that fails or times out gives Persona-only Recollection and a Trace line.
- Live (paid, explicit run): a real embedding call round-trips and the cost event is recorded.

**Verification:**
- The same offline memory scenarios pass against both adapters through one parameterised suite.

### Phase 4: Capture, the page, and proof

- [ ] **Unit 10: Capture**

**Goal:** Full prompts and replies per step for debugging, off by default and never for a Run that has read a file.

**Requirements:** R20, R16, N1

**Dependencies:** Units 1, 4

**Files:**
- Create: `src/stepout/capture.py`
- Modify: `src/stepout/runner.py` (write after each model call unless Tainted)
- Modify: `src/stepout/app.py` (the keeper removes Capture with its chat)
- Modify: `.env.example`
- Test: `tests/test_capture.py`

**Approach:** Opt in with `STEPOUT_CAPTURE=1`; one JSONL file per Run under `data/capture/`; text passes through `redact`; once the Run is Tainted nothing more is written, and a Run that began Tainted writes nothing.

**Test scenarios:**
- Off by default writes nothing; on writes one line per model call with request and response.
- After a file read no further line is written; a Run that builds on a Tainted exchange writes none.
- A secret-looking value is `[redacted]` in the file.
- Deleting the chat removes the file; the age sweep removes old files.

**Verification:**
- A Run that read a planted file leaves no file text in `data/capture/`.

- [ ] **Unit 11: The page**

**Goal:** The page exposes what the backend now offers: chat management, Memory, and visible retries.

**Requirements:** R24, R26, R12, R13

**Dependencies:** Units 5, 7, 9

**Files:**
- Modify: `web/src/Sidebar.tsx` (rename, delete with a confirmation naming what goes, search box)
- Create: `web/src/MemoryView.tsx` (Persona editor, learned and History entries with Forget)
- Modify: `web/src/RunBlock.tsx` (retry line, "Memory used", tokens and time)
- Modify: `web/src/protocol.ts`, `web/src/useBackend.ts`, `web/src/store.ts` (additive types and calls)
- Modify: `src/stepout/channels/web.py`, `src/stepout/contract.py`, `docs/ui-contract.md` (`GET /api/memory`, persona update, `DELETE /api/memory/{id}`)
- Modify: `web/mock/` fixtures and `web/e2e/` flows
- Test: `web/src/Sidebar.test.tsx`, `web/src/RunView.test.tsx`, new `web/src/MemoryView.test.tsx`, `tests/test_web_channel.py`, `tests/test_contract.py`

**Approach:** Additive fields only, as the contract allows. Rebuild the page (`cd web && npm run build`) and verify every flow in real Chrome, not only over the WebSocket (ADR 0013). A swept or deleted screenshot must not break a chat.

**Test scenarios:**
- Rename and search update the list; delete asks first and removes the chat; the list recovers when the delete is refused.
- The run card shows "Provider busy, retrying in 4 s (2 of 3)" from `retry` events and "Memory used (n)" from the `memory` event; unknown kinds are still ignored.
- Persona edits save and appear in the next Recollection; Forget removes an entry and the list updates.
- Narrow (phone) layout keeps the new controls usable.

**Verification:**
- Each flow performed in the real page with screenshots as evidence.

- [ ] **Unit 12: The comparison harness and the docs**

**Goal:** The success criteria can be measured and the docs say what is true.

**Requirements:** Success Criteria, R2, R9, R25, N10

**Dependencies:** Units 2, 9, 11

**Files:**
- Modify: `scripts/acceptance.py` (`--memory off|files|mem0`, a fault-injection mode, a comparison table in the report)
- Create: `tests/data/memory_tasks.jsonl` (the three "second chat" tasks and a Persona fixture)
- Modify: `tests/support/acceptance_offline.py`, `tests/test_acceptance.py`
- Modify: `docs/architecture.md` (modules, seams, safety model, ceilings), `docs/history.md`, `docs/roadmap.md`, `src/stepout/CONTEXT.md`, `CLAUDE.md`, `docs/adr/README.md`

**Approach:** Offline runs are the gate and cost nothing. The live comparison (three conditions over eleven tasks, roughly the cost of three acceptance runs) is run only with the User's explicit go-ahead on spend.

**Test scenarios:**
- Offline harness passes in all three memory modes and in fault mode.
- The report contains one table: actions and cost per task per condition, and the injection check.

**Verification:**
- The offline suite is green; the roadmap's "Next, in order" list and the glossary match what exists.

## System-Wide Impact

- **Interaction graph:** the wrapper touches Screening, the Searcher and the Runner at once; `app.run` gains commands, month check, extraction and `learn`; the web channel gains routes; the Orchestrator's context gains one block.
- **Error propagation:** retryable `Failure` kinds are absorbed by the wrapper until bounds are hit, then surface as today's plain lines; Memory and Log failures never fail a Run; a refused delete answers 409.
- **State lifecycle risks:** a purge is transactional for the database and best-effort for files; Qdrant's local store is single-process and must be closed on exit; interrupted-Run closing assumes one process per data folder.
- **API surface parity:** the terminal channel gets commands and Recollection; Persona editing and entry listing exist there only through commands and the file; the page gets the Memory view.
- **Integration coverage:** a real-Chrome pass for delete, rename, search, Memory view and retry display; a fault-injected acceptance run; a cross-chat provenance test through the real `app.run` and Store.
- **Unchanged invariants:** the Gate, Taint, the read-only rules, the $1 per-Run cap, one Run at a time, the reply being saved before it is sent, and "a model with no price fails the Run".

## Risks & Dependencies

- **Mem0 API drift and the 2.x line's behaviour** (search signature, metadata filters): pinned exactly; adapter isolated behind the seam; the file baseline keeps the product working if it must be dropped.
- **Windows install weight and local Qdrant** (`grpcio`, `numpy`, file locking): the factory falls back with a start-up note; the store is closed on exit; confirmed with a dependency dry-run only, not yet an install.
- **A second provider sees the User's messages** (embeddings): disclosed in the start-up note and the Trace; the embedder is a configuration value.
- **Memory poisoning through a message the User pastes** (their own act, but it may contain a web page's instructions): Recollection is framed as data, every write is visible and forgettable, and the Gate does not read Memory.
- **SDK retries that cannot be disabled for some provider**: counted by a request-level test, written down as a ceiling if found, with the attempt count adjusted.
- **Retries raising spend or latency**: bounded per call and per Run, checked against the cap, visible in the Trace.
- **Purge is irreversible**: confirmation in the page; refused while the chat is live; the backup rule covers migrations only (not purges), by design.
- **Live spend**: the paid comparison and the live memory check need the User's go-ahead, and `OPENAI_API_KEY` must be added to `.env` by the User (never read by the assistant).

## Documentation / Operational Notes

- New ADRs: 0015 (retry policy) and 0016 (Memory on Mem0 behind the seam, extraction through our Model port); amend 0003's status.
- Update in the same commit as behaviour: `docs/architecture.md`, `docs/ui-contract.md`, `src/stepout/CONTEXT.md`, `docs/roadmap.md`, `docs/history.md`, `CLAUDE.md`, `.env.example`.
- After pulling `pyproject.toml`: `pip install -e ".[dev]"` again (adds `mem0ai`).
- New environment variables: `STEPOUT_MEMORY`, `STEPOUT_CAPTURE`, `STEPOUT_LOG_LEVEL`, `STEPOUT_MONTH_CAP_USD`, and `OPENAI_API_KEY` for Mem0.
- Roadmap order after this: Questions, Approvals and pause/resume; Notes; the Pydantic AI parity run; the Evaluation harness running Memory on/off and faults.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-10-11-record-and-memory-requirements.md](../brainstorms/2026-10-11-record-and-memory-requirements.md)
- Related code: `src/stepout/runner.py`, `src/stepout/model.py`, `src/stepout/pydantic_model.py`, `src/stepout/screening.py`, `src/stepout/ledger.py`, `src/stepout/history.py`, `src/stepout/channels/web.py`, `src/stepout/capabilities/fetch.py`
- ADRs: [0003](../adr/0003-memory-files-first.md), [0004](../adr/0004-drop-zero-model-replay.md), [0006](../adr/0006-sqlite-for-runs-and-ledger.md), [0011](../adr/0011-pydantic-ai-as-the-plumbing.md), [0012](../adr/0012-the-front-door.md), [0013](../adr/0013-the-reply-streams.md)
- External docs: Mem0 open source (add, search, get_all, delete, AsyncMemory, telemetry, Qdrant config); Pydantic AI (retries, `ModelHTTPError.retry_after`, instrumentation)
