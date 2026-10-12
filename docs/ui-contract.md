# UI contract: what the page and the backend promise each other

The wire between the React page (`web/`) and the backend (`src/stepout/channels/web.py`). The types are `src/stepout/contract.py` (Pydantic, `extra="forbid"`); a test validates every file in `web/fixtures/` against them, so a fixture and the backend cannot drift apart silently. This file and `contract.py` change together.

## Rules for evolving it

1. **Additive changes are free**: a new optional field, a new trace `kind`, a new endpoint. The page **must ignore** unknown fields and kinds.
2. Renaming or removing something, or changing a meaning, bumps `v` (the `hello` frame).
3. Events are the one record. The page renders a live Run and a past Run from **the same event shape**.

## Transport

`GET /` serves `web/dist/index.html`. `GET /ws` is a WebSocket on `127.0.0.1:8765` (`STEPOUT_PORT` changes the port); its `Origin` must be our own or absent. The server's first frame is `{"type": "hello", "v": 1}`.

**Page to server** (JSON text frames, at most 64 KB):

| Frame | Meaning |
|---|---|
| `{"type": "send", "conversation_id": "…", "text": "…"}` | send a message in a chat (at most 20,000 characters) |
| `{"type": "stop"}` | stop the active Run (it ends within about a second, even inside a model call, a read or a page load) |

**Server to page** (every frame but `hello` has `at`, an ISO-8601 UTC time):

| Frame | Fields |
|---|---|
| `message` | `id`, `conversation_id`, `role` (`user`/`assistant`), `text`, `run_id` and `cost_usd` (assistant only). No cost footer in `text` (an older saved reply may carry one; the page strips it) |
| `trace` | `id`, `conversation_id`, `run_id`, `parent` (the `step` event that started this Role's work, or null), `kind`, `role`, `data`, `cost_usd` |
| `status` | `state: idle\|running`, `active: {conversation_id, run_id, cap_usd} \| null`, `queued: [{conversation_id}]`. One Run runs at a time across all chats |

### Trace kinds

| `kind` | `role` | `data` |
|---|---|---|
| `plan` | `orchestrator` | `summary`, `steps: [{role, goal, status: pending\|running\|done\|failed}]`; sent on every change |
| `step` | the acting Role | `summary` (e.g. `web_search new york news`, `browse open https://…`, `answer`), `action: {kind, …}`, `verdict: allow\|refuse\|ask`; `cost_usd` is that model call. A skipped repeat says `repeat, not run again` and carries `repeat: true`; also `model`, `input_tokens`, `output_tokens`, `duration_ms`, `attempts` (tries the call took) and `prompt_chars` (the size of what the model was sent, never its text) |
| `result` | the acting Role | `summary` (`fetch: 1840 characters`), `chars` (the size of what the tool gave the Role), `duration_ms`, `cut` (it reached the length limit). A size, never the tool's text; its `parent` is the `step` that asked for it |
| `return` | the specialist | `summary` (`done: …` / `failed: …`, first 200 characters), `ok` |
| `shot` | `browser` | `summary`, `shot: "<run_id>/<n>.jpg"` (fetch from `/shots/`), `url` and `title` of the page shown |
| `stop` | the Role that stopped | `summary` (`Stopped by you.` or the budget message) |
| `error` | the Role that was acting | `summary` (the plain line the User is also given as the reply), `cause` (`auth` `no_key` `credit` `rate_limit` `overloaded` `server_error` `timeout` `connection` `rejected` `malformed` `pricing` `no_search` `chrome` `interrupted` `internal`), `type` (the exception class, for the Ledger), `status` (HTTP, if any); emitted just before a Run ends `failed`. `interrupted`: written at the next start for a Run the app's stopping cut off |
| `retry` | the Role that was acting | `summary` ("The provider is busy; trying again in 2 s (2 of 3)"), `attempt` (the one that failed), `of` (attempts allowed), `cause` (an `error` cause), `status` (HTTP, if any), `wait_s`, and `repair: true` when the reply was unreadable and is being asked for again (no wait); a tool's retry has `cause` set to the error's class; `cost_usd` is what the failed attempt may have cost ([ADR 0015](adr/0015-one-retry-policy-at-the-model-port.md)). A page that does not know the kind ignores it |
| `memory` | `orchestrator` | `summary`, `op` (`recall` at the start, `record` after the reply), `ok`; a successful recall has `ids` (what Memory handed over), `chars` and `ms`, and `skipped` if it was cut; a failed one has `cause`. Memory never fails a Run: a failure is this line and the Run goes on ([ADR 0016](adr/0016-memory-on-mem0-behind-the-seam.md)) |
| `delta` | `orchestrator` | `text` (the next words of the reply), or `reset: true` (what came so far was not the answer: drop it). **Live only**: never saved or replayed; the finished reply still arrives as a `message`, which replaces the words shown. Not sent for a Run that has read a file ([ADR 0013](adr/0013-the-reply-streams.md)) |

`screening` events exist in the Ledger but are not streamed.

## HTTP (JSON, read-mostly)

| Route | Returns |
|---|---|
| `GET /api/conversations` | `[{id, title, updated_at, preview, state}]`, newest first. `title` is the first request cut to 60 characters. `state` is `idle`, `queued` or `running` |
| `POST /api/conversations` | `201` with `{id}`: a new empty chat (not stored until its first message is saved) |
| `GET /api/conversations/{id}` | `{id, title, messages: [message…], runs: [{run_id, request, state, cost_usd, cap_usd, steps, started_at, ended_at}]}`; run `state` is `running\|done\|stopped\|failed` (an over-budget Run is `stopped`, with the reason in its `stop` event). A Run left open by a crash reads `failed` unless it is the live Run |
| `GET /api/conversations?q=text` | the same list, only chats whose title or any message contains `text` (case-insensitive; a Run's trace is not searched) |
| `PATCH /api/conversations/{id}` | body `{title}` (1 to 120 characters): rename; `200 {id, title}`, `422` for a bad title, `404` unknown. Needs `Origin` and JSON like `POST` |
| `DELETE /api/conversations/{id}` | purge the chat: its messages, Runs, events and screenshots (and what Memory learned from it): `204`, `404` unknown, `409` while it has a Run in progress or waiting. Needs `Origin`. **Not undoable**: the page asks first |
| `GET /api/conversations/{id}/export` | the chat as Markdown (`text/markdown`, attachment): title, then each message in order; no trace data |
| `GET /api/runs/{run_id}/events` | `[trace…]` in order: exactly what was streamed live (minus `delta`). `404` for an unknown Run or one with no events yet |
| `GET /shots/{run}/{n}.jpg` | a page screenshot (`run` is 32 hex characters; only files the assistant wrote; JPEG quality 50, viewport 1000×700) |
| `GET /live/{run_id}` | the live browser view, below |

Ids are 32 lowercase hex characters, plus the literal `default` (the terminal's chat); anything else answers `404` before any lookup. Not in the contract: renaming or deleting chats, search, attachments.

## Behaviour worth knowing

- **`status` between a message and its Run.** `state` is `running` as soon as a message is taken from the queue; `active` stays `null` until the Run's first event arrives (screening takes about a second), then carries the run id and `cap_usd`. A `status` frame is sent only when the queue or the active Run changes, not per event.
- **Queued messages** are echoed at once as a `message` frame, and are not saved until their turn; a chat read back includes them, and a chat whose first message is queued is listed with `state: "queued"`.
- **A reply's live frame** carries the id and time of its saved copy, so the live and the replayed chat are one message. A user message's echo goes out before it is saved, so its id differs; the page treats history as the record.
- **Client frames** are validated by `contract.py`: a stray field, a missing `text`, a text over the limit, or an unknown chat is ignored (no error frame).

## Live view

The User sees the assistant's headless browser while it works. View-only: nothing the page does reaches the browser.

`GET /live/{run_id}` returns `multipart/x-mixed-replace; boundary=frame`: `image/jpeg` parts, the newest frame at once and then each new one, ending with the closing boundary `--frame--` when the Run ends or the server stops. A slow client skips frames it missed; nothing is stored (the `shot` events are the record). `404` for an id that is not 32 hex characters or a Run that is not active. In the page: `<img src="/live/<run_id>">` while the Run is running and has a Browser step, then the Run's last `shot`.

Behind it, `Browser(shots=..., on_frame=cb)` calls `cb(run_id, jpeg)` (synchronous, non-blocking, at most four a second per Run, no larger than the viewport); `app.py` passes the channel's `live_frame`.

## Security (each is a test)

- Every `/api`, `/live` and `/ws` request must carry a `Host` of `127.0.0.1:<port>` or `localhost:<port>` (blocks DNS rebinding).
- `POST` requires `Content-Type: application/json` and an allowed `Origin`; no CORS headers are ever sent.
- Ids are server-generated and validated before any lookup; screenshot paths are never built from user input.
- Model output is untrusted: the page renders markdown **without raw HTML or images**, allows only `http(s)` and `mailto` links, and sets `rel="noopener noreferrer"`.

## Not built yet

`{"type": "question", …}` and `{"type": "approval", …}` frames and page-to-server `answer` / `approve` frames arrive with pause and resume ([roadmap](roadmap.md)); the page ignores them until then.

## Fixtures

`web/fixtures/` holds recorded or hand-made runs in this shape: a web run with screenshots, a Files run (invented paths only: **never** real paths from a Ledger), a refused action, a Stop, an over-budget stop, a decline. The mock server (`web/mock/`) replays them for page development and tests with no key and no spend.
