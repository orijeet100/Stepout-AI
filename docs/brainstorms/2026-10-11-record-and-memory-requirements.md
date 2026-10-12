---
date: 2026-10-12
topic: record-and-memory
---

# Iteration 2: Memory on Mem0, a managed Record, and precise retries

## Problem Frame

V0 does one chat at a time and every new chat starts from zero. The Assistant does not know where the User's Documents live, what they prefer, or what it did for them yesterday, so the User re-names folders and re-states context (the Local File Finder refuses a drive-wide search and asks for a folder every time).

The Record exists but cannot be managed or trusted yet:

- **No log file.** Failures outside a Run (`trace frame not sent`, `request failed`) go to the terminal and vanish with it.
- **Saved chats can't be managed.** They can be listed and opened, but not renamed, deleted, searched or exported. Screenshots in `data/runs/` grow forever.
- **A crash leaves a Run "running" in the database.** The page hides it at view time; the row stays open.
- **Steps carry cost but no tokens, durations or attempts.** So we cannot tell what Memory costs, how long a step took, or how often a call was retried.
- **Retries are implicit and different per adapter.** The Anthropic adapter relies on the SDK's own defaults (`_explain` says "the SDK has already retried what is worth retrying"); the Pydantic AI adapter adds none of its own and gets whatever its provider SDK does. Nothing is recorded, a malformed reply fails the whole Run, and a failed attempt's cost may not be counted against the $1 cap.

This iteration gives the Assistant a small, inspectable Memory (Mem0 behind the existing seam), gives the User a Record they can manage, records every step and attempt, and replaces implicit retries with one written policy. It is also the first step toward the headline claim, *asks less over time* ([ADR 0004](../adr/0004-drop-zero-model-replay.md)): Memory must be switchable off so it can be measured.

### The shape: four layers, four jobs

| Layer | Job | Seen by | Written by | Form |
|---|---|---|---|---|
| **Memory** (new) | what the Assistant knows going into a Task | the model (as Recollection), the User | the User; code from a Run's outcome; Mem0's extraction **from the User's own messages only** | Persona: a Markdown file. Learned facts and History: Mem0, local |
| **Ledger** (exists, extended) | what happened: steps, attempts, cost, time: audit, Trace, Evaluation | the page, Evaluation; never the model | the Runner | SQLite events (no file contents) |
| **Log** (new) | how the app behaved: errors, startup, timings | the developer and the User | code | one rotating file |
| **Capture** (new, off by default) | full prompts and replies per step, for debugging | the developer | the Runner, only when switched on | local JSONL, short retention, never for a Run that read a file |

Saved chats are the User's view of the Ledger's message events, not a fifth store.

## Requirements

**Memory (Mem0 behind `recall` / `remember` / `forget`)**

- R1. **Persona stays a file.** The User keeps facts and preferences (including "where my usual Documents live") in a plain Markdown file they can open and edit. A line the User wrote is Pinned: nothing overwrites it. Persona is always in Recollection and is not stored in Mem0, so the User's edits are the source of truth.
- R2. **Mem0 holds the learned layer.** Facts extracted from the User's messages and History entries live in Mem0, local only. A plain-file store (Persona plus an appended History file) remains the baseline adapter, chosen by one environment variable, so the two compare on the golden set (the "measured challenger" of [ADR 0003](../adr/0003-memory-files-first.md)).
- R3. **What Mem0 may be fed.** Extraction runs only on the User's own messages. History entries are written by code from a Run's outcome and stored verbatim, with no model in the write path. Replies, Findings, tool results, web text and file text are never fed to it (a test for each: a planted injection in a web page and in a file leaves Memory unchanged).
- R4. **Writes are visible.** After a Run, anything written to Memory appears as a line in the Trace with the message it came from, and in `/memory` with an id.
- R5. **Commands in both channels.** `/remember <fact>` adds a pinned Persona line; `/memory` lists everything with ids and provenance; `/forget <id>` removes one entry and says what it removed. No silent fuzzy delete.
- R6. **Recollection.** At Run start the Orchestrator is handed the Persona plus the few most relevant learned entries, within a fixed size budget and one search call. The Trace shows what was handed (entry ids and size). If Memory is slow or down (hard time limit), the Run goes ahead with Persona only and the Trace says so: Memory never blocks a Task.
- R7. **Memory is data, not authority.** Recollection is presented as facts about the User. It cannot widen Grants, the Gate's rules, the Role's tools or the web.
- R8. **Tainted Runs leave a thin entry.** A History entry from a Run that read file contents holds the request and outcome only: no reply text, no file-derived details. File contents cannot cross chats through Memory.
- R9. **Memory off.** One switch gives a Run an empty Recollection and writes nothing, so the same Task runs with and without Memory (a Condition for Evaluation).
- R10. **Mem0 is local.** Its telemetry is disabled, and its vector store and history database sit under `data/memory/`. The hosted Mem0 platform is not used.
- R11. **Mem0's own model calls are metered.** Extraction and embedding calls count in the Ledger and against the Run's cap (or a Memory cap), obey Stop, and follow the retry policy below. A cost that cannot be seen is not allowed to exist.

**Record**

- R12. **Manage chats.** Rename, delete and search by text; export one chat as Markdown (should).
- R13. **Delete means delete.** Deleting a chat is User-initiated only, asks once, says what will go, and removes its messages, Runs, events, screenshots, Capture files and History entries. `/forget` only edits Memory and never touches the Ledger. "Append-only" now means the Assistant never edits the Ledger; the User may purge.
- R14. **No Run left running.** A Run still open when the process died is closed as `interrupted` at the next start, with a plain line.
- R15. **App log.** One rotating file under `data/logs/`: startup configuration, every failure including those outside a Run, chat and run ids on each line, level set by an environment variable. Never file contents, secrets, prompts or replies.
- R16. **Retention.** Screenshots and Capture files go with their chat or after a stated age (default 30 days).
- R17. **Monthly cap** (should). A month's spend, summed from the Ledger, is checked when a Run starts; at the cap the Run is refused with a plain line.

**Steps and intermediate steps**

- R18. **Every step is fully described, without contents.** Each step event records Role, action, verdict, model, input and output tokens, duration, attempt count, cost and (for a tool) the result's size and whether it was truncated. Existing rules stay: file paths and sizes, never file text.
- R19. **Handoffs are recorded.** What an agent passed on (a Finding, the notes the Orchestrator was given, the Recollection handed over) is recorded as ids and sizes, so a Run's decisions can be reconstructed from the Ledger alone.
- R20. **Capture, off by default.** When switched on, each step's full prompt and model reply go to a local JSONL file per Run. Secret-looking values pass through the existing redaction first. Capture is never written for a Run that read a file's contents, and is deleted with its chat or by age (R16).

**Retry: one written policy**

- R21. **One owner.** Retries for model calls happen in one place at the Model port, with the same policy for every adapter. SDK-level retries are switched off so there is exactly one policy, and every attempt is visible.
- R22. **Classified, not guessed.** Each Failure kind declares whether it is retryable. Defaults:

| Situation | Retry? | Attempts (total) | Wait | If it still fails |
|---|---|---|---|---|
| 429 rate limit | yes | 3 | the provider's `Retry-After` if given (cap 30 s), else backoff | "rate-limiting, wait a minute" |
| 500, 502, 503, 504, 529 overloaded | yes | 3 | exponential with jitter, about 1 to 8 s | server-busy line |
| Connection reset or timeout before any byte | yes | 3 | as above | connection line |
| Failure after words reached the page | once, after the page discards the streamed text | 2 | about 1 s | fail; partial reply discarded |
| 400, 413, 422 rejected | no | 1 | none | "rejected" line |
| 401, 403, 402, no key, no known price | never | 1 | none | fix-it line; the Run is not started |
| Malformed reply or invalid tool call | one repair: the error is fed back | 1 per step, 3 per Run | none | "could not be understood" |
| Read-only tool: timeout, connect error, 5xx, 429 | yes | 2 | about 1 s with jitter | the Role gets a failed Finding |
| Gate refusal, 4xx, content errors | no | 1 | none | the Role sees the refusal |
| Any Consequential Action (later) | **never** | 1 | none | "outcome unknown, please check" |
| Memory recall | no retry; 3 s limit | 1 | none | continue without Memory (R6) |
| Memory or SQLite write | once; never fails the Run | 2 | about 200 ms | logged, shown in the Trace |
| The whole Run | never automatic | n/a | n/a | the User re-sends; Resume comes with Checkpoints |

  The numbers are starting values to calibrate with the fault tests below.
- R23. **Bounded.** All retries in one Run together wait at most 60 s and happen at most 8 times. Retries never push spend past the cap, and a failed attempt's cost is counted when the provider reports it. Stop ends a backoff sleep at once.
- R24. **Visible.** Every attempt is a `retry` event (attempt, cause, status, wait, cost) in the Ledger. The page shows "Provider busy, retrying in 4 s (2 of 3)". The run summary keeps retry count and total wait.
- R25. **Proved offline.** A fault-injecting model double drives every row of the table with a fake clock: attempts, waits, Ledger rows, cost, a stream cut mid-reply, Stop during a backoff, and the budget cap.

**Page** (second slice)

- R26. A Memory view: Persona editable, learned entries listed with Forget, and the run card shows "Memory used" and retries for the Run.

## Non-functional Requirements

| # | Quality | Requirement |
|---|---|---|
| N1 | **Privacy** | Memory, Ledger, Log and Capture stay on the laptop under `data/` (git-ignored). What may leave: the Recollection inside a model prompt, and the text sent to the embedding provider the User chose. Both are named in the Trace or settings; Mem0 telemetry is off. |
| N2 | **Safety** | Gate, Taint and the read-only rules are unchanged and each new rule above has a test (the project's convention). Memory off cannot be bypassed by a message. |
| N3 | **Cost** | Recollection and extraction use cheap-tier calls, are metered (R11), and are bounded. Target, to calibrate on the first run: Memory-on within +10% of Memory-off on the acceptance queries. |
| N4 | **Ownership** | Persona and the baseline History are plain, human-readable files; deleting `data/memory/` is Memory off; the User's edits survive upgrades. Mem0's vectors are not readable, so `/memory` is the readable view of them. |
| N5 | **Reliability** | The retry policy (R21 to R25) is the specification; behaviour under injected faults is measured, not promised. A Memory or log failure never fails or hides a finished Run. The reply is still saved before it is sent. |
| N6 | **Durability** | File writes are atomic (a crash never corrupts Persona). SQLite is opened so a second reader or a crash cannot lose a committed Ledger row. |
| N7 | **Scale** | Usable after a year of daily use (about 1,000 Tasks): the chat list, chat search and Recollection each finish well under a second, with no per-chat query. (The list is N+1 today; confirm the numbers in planning.) |
| N8 | **Compatibility** | Existing `data/stepout.db` and saved chats open unchanged. Migrations are additive and a backup is taken first (the `.bak-before-v5` and `-v6` copies were made by hand). |
| N9 | **Observability** | Ledger answers "what did it do and how long did it take"; Log answers "what went wrong"; Capture answers "what exactly was said". None is Memory. |
| N10 | **Testability** | Offline suite with the scripted model; Memory on/off and the Mem0/files choice are environment switches; Mem0 runs against a temp folder in tests; Evaluation reads Memory only through a Channel and the Ledger ([context map](../../CONTEXT-MAP.md)). UI work is verified in the real page. |
| N11 | **Maintainability** | Memory sits behind `recall` / `remember` / `forget` with two adapters; one ADR for the shape and one for the retry policy; glossary entries flip from *(planned)*; docs in the same commit. Mem0 is pinned to an exact version. |

## Success Criteria

- On the 8 acceptance queries plus 3 new "second chat" tasks (for example "find my resume" after the User said where Documents live), Memory-on takes fewer Actions or less money than Memory-off on the Persona-sensitive tasks and does not regress the rest, for both adapters, in one comparison table.
- The planted-injection acceptance query still passes and no Memory write comes from Untrusted content.
- The User can answer "what does it know about me?" with one command and remove any item with one command.
- Kill the process mid-Run: at restart no Run shows as running, and the log explains the failure with ids.
- Every row of the retry table has an offline test; no Run exceeds its cap because of retries; every retry is visible in the Trace and the Ledger.
- A Run can be reconstructed step by step from the Ledger alone, without file contents.

## Scope Boundaries

- No Notes yet (Assistant-written site know-how with expiry): they need write rules for Untrusted content, the riskiest part. Mem0's expiry date would carry them later.
- No hosted Mem0, no graph memory, no Mem0 fed from replies or tool output.
- No Questions, Approvals or pause/resume (roadmap item 2 stays next). "Asks less" cannot be measured directly yet; the baseline uses Actions, cost and folder-restating.
- No Telegram, multi-user, cloud backup, encryption at rest or external observability service. The Ledger is shaped so one can be attached later (see Alternatives).
- The Pydantic AI parity run and removing the second adapter stay on the roadmap. The retry policy is written once at the Model port so it does not wait for it.
- No automatic whole-Run retry and no circuit breaker: both double spend or add machinery for one user.

## Key Decisions

- **Mem0 in this iteration, behind the seam, with a file baseline.** The User chose it. The seam was designed for it, and two adapters make a measured comparison possible, which is the point of the project.
- **Mem0 extracts from the User's messages only.** That keeps the Provenance rule ([ADR 0003](../adr/0003-memory-files-first.md)) true: the one place a model writes Memory is a transformation of the User's own words, and every write is visible and forgettable.
- **Embedder: OpenAI `text-embedding-3-small`.** Cents a month and nothing to install. Cost: the User's messages go to a second provider, so an `OPENAI_API_KEY` joins `.env` and the Trace names the embedding calls. The embedder is a config value, so a local one can replace it, at the price of re-embedding.
- **Extraction input is the User's messages only, on the cheap tier.** Not replies, not Findings, not tool output. Widening it later is a new decision.
- **History is written by code, verbatim, without inference.** Free, deterministic, explainable.
- **Persona stays outside Mem0.** Pinned lines must be exactly what the User wrote.
- **One retry owner at the Model port.** Today's two implicit behaviours become one policy that is recorded, bounded and testable.
- **The User may purge the Ledger; the Assistant never edits it.** The glossary's "append-only" entry needs amending in the same change.
- **Measurement fields land first** (tokens, durations, attempts, interrupted Runs): Memory's value cannot be shown without them.

## Alternatives Considered: chat persistence and step logging

| Option | Verdict |
|---|---|
| **SQLite (keep) with WAL and full-text search** | **Recommended** for chats and the Ledger: one file, additive migrations, already built ([ADR 0006](../adr/0006-sqlite-for-runs-and-ledger.md)). |
| Postgres | Not until a second machine or many users write (ADR 0006). |
| Langfuse (cloud or self-hosted) | Not now: hosted sends prompts off the laptop; self-hosted is a multi-service stack for one user. Add later as an exporter from the Ledger. |
| OpenTelemetry or Logfire spans | Pydantic AI can emit model-call spans (`include_content=False` keeps prompts out), but a collector for one process buys little over Ledger columns. Revisit with the exporter above. |
| Standard-library `logging` with a rotating file | **Recommended** for the Log; `structlog` and `loguru` add a dependency for what the standard library does. |
| Mem0 hosted platform | Rejected: memory text would leave the laptop (N1). |

## Outstanding Questions

### Resolve Before Planning

None. Resolved 2026-10-12: the embedder is OpenAI `text-embedding-3-small`; Mem0's extraction sees the User's messages only (see Key Decisions).

### Deferred to Planning

- [Affects R6][Technical] How relevance is chosen and the size budget; whether Persona and History share one Recollection format.
- [Affects R1, R5][Technical] Persona file format and how `/remember` edits it without disturbing the User's own text.
- [Affects R11][Needs research] Whether Mem0's LLM and embedder can be routed through our Model port, or must be metered by reading their usage; Mem0's current `add` semantics and exact version to pin.
- [Affects R10][Needs research] Local Qdrant limits and Windows install; the default store path is `/tmp/qdrant`, so the path must be set explicitly.
- [Affects R21][Needs research] How to switch off SDK-level retries on both adapters and what the Pydantic AI version in use does by default.
- [Affects R18][Technical] Whether tokens, durations and attempts go in the event's data or in new columns.
- [Affects R12][Technical] Full-text search method and whether chat messages move out of the events table.
- [Affects R15, R20][Technical] Whether `redact.py` is reused on log lines and Capture; rotation sizes.
- [Affects R16][Needs research] Retention defaults.

## Beyond this iteration (what else needs improving)

| Item | Why | Trigger |
|---|---|---|
| Questions, Approvals, pause/resume | the only way to measure "asks less"; unlocks the first write | right after this iteration |
| Notes (Assistant-written, expiring) | the second half of Memory | Persona and learned memory measured |
| Pydantic AI parity run, delete `AnthropicModel`, stream on one adapter | two adapters, only one streams | any time, about $0.30 |
| Evaluation harness running Memory on/off and fault injection | turns the baseline into the headline number | after R9, R18 and R25 |
| Debt: Roles wired by name in the Runner; "no file contents" flag set inside `read_text`; Orchestrator prompt lists Roles by hand | each contradicts "a tool is one file plus one line" | when a tool is next added |
| Orchestrator over-plans; Direct step cap (5) untuned | known ceiling | Evaluation data |
| Names and paths from `list`/`find` go to the model API | privacy ceiling | before any second User |
| Fetcher: DNS rebinding between check and connect | security ceiling | before any non-read-only web action |

## Next Steps

→ Resolve the two questions above, then `/ce:plan`.
