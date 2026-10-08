# UI contract — what the page and the backend promise each other

Status: **v0 verified from the code (2026-10-07); v1 frozen at sync X1 on 2026-10-07** (the User signed it off; see [the log entry](log/2026-10-07-ui-contract-v1-frozen.md)). Owners: the UI lane owns `web/` and `channels/web.py`; the Main lane owns what produces the data. A change to this file is a `contract` entry in [`log/`](log/README.md) and needs both lanes to notice it at the next sync ([`plan/README.md`](plan/README.md)).

## Rules for evolving it

1. **Additive changes are free**: a new optional field, a new event `kind`, a new endpoint. The page **must ignore** unknown fields and unknown kinds.
2. Renaming or removing something, or changing a meaning, bumps `v` and needs a `contract` log entry.
3. Events are the one record. The page renders a live run and a past run from **the same event shape**.
4. The Main lane writes `src/stepout/contract.py` (the wire types as Pydantic models, iteration B2). A test validates every file in `web/fixtures/` against it, so a fixture and the backend cannot drift apart silently.

## v0 — what exists today (verified)

**Transport.** `GET /` serves `web/dist/index.html`. `GET /ws` is a WebSocket on `127.0.0.1:8765`; its `Origin` must be our own origin or absent. `GET /shots/{run}/{n}.jpg` serves page screenshots (`run` is 32 hex characters, only files the Assistant wrote; JPEG quality 50, viewport 1000×700). On connect the server replays its in-memory history; after a restart it is gone.

**Page → server** (JSON text frames, max 64 KB): `{"text": "..."}` sends a message; `{"stop": true}` asks the running Run to stop (checked between steps).

**Server → page:**

```jsonc
{"role": "user" | "assistant", "text": "..."}     // chat messages; the assistant text ends with "\n\n(cost: $0.0932)"
{"type": "trace", "kind": "...", "role": "...", "data": {...}, "cost_usd": 0.0064}
```

| `kind` | `role` | `data` |
|---|---|---|
| `plan` | `orchestrator` | `summary`, `steps: [{role, goal, status: pending\|running\|done\|failed}]` — sent on every change |
| `step` | the acting Role | `summary` (e.g. `browse open https://lu.ma/discover`, `answer`), `action: {kind, ...}`, `verdict: allow\|refuse\|ask`; `cost_usd` is that model call |
| `return` | the specialist | `summary` (`done: …` / `failed: …`, first 200 chars), `ok` |
| `shot` | `browser` | `summary`, `shot: "<run_id>/<n>.jpg"` (fetch it from `/shots/`) |
| `stop` | the Role that stopped | `summary` (`Stopped by you.` or the budget message) |
| `error` | the Role that was acting | `summary` (the plain line the User is also given as the reply), `cause` (`auth` `no_key` `credit` `rate_limit` `overloaded` `server_error` `timeout` `connection` `rejected` `malformed` `chrome` `internal`), `type` (the exception class: for the Ledger, not for display), `status` (HTTP, if any). Added 2026-10-08, additive: emitted just before a Run ends `failed` |

`screening` events exist in the Ledger but are not streamed. A trace carries no run id, event id, parent or time yet (the run id is inside `shot`).

## v1 — frozen at X1

Everything in v0 keeps working until the page moves over (the old frames are accepted for one release).

### WebSocket `/ws`

Server's first frame: `{"type": "hello", "v": 1}`.

Page → server:

| Frame | Meaning |
|---|---|
| `{"type": "send", "conversation_id": "…", "text": "…"}` | send a message in a chat |
| `{"type": "stop"}` | stop the active Run |

Server → page (every frame has `at`, an ISO-8601 UTC time):

| Frame | Fields |
|---|---|
| `{"type": "message"}` | `id`, `conversation_id`, `role` (`user`/`assistant`), `text`, `run_id` (assistant only), `cost_usd` (assistant only; **no cost footer in `text`** once the Main lane drops it — until then the page strips `\n\n(cost: $…)`) |
| `{"type": "trace"}` | everything in v0 **plus** `id`, `conversation_id`, `run_id`, `parent` (the `step` event id that started this Role's work, or null). A `shot` event's `data` also carries `url` and `title` of the page shown, so the viewer can caption it. |
| `{"type": "status"}` | `state: idle\|running`, `active: {conversation_id, run_id, cap_usd} \| null`, `queued: [{conversation_id}]` — one Run runs at a time across all chats ([log](log/2026-10-07-one-run-at-a-time.md)); `cap_usd` (the Run's budget) is what the progress meter compares spend against |

### HTTP (JSON, read-mostly)

| Route | Returns |
|---|---|
| `GET /api/conversations` | `[{id, title, updated_at, preview, state}]`, newest first. `title` is the first request cut to 60 characters. `state` is `idle`, `queued` or `running`. |
| `POST /api/conversations` | `{id}` — a new empty chat. |
| `GET /api/conversations/{id}` | `{id, title, messages: [message…], runs: [{run_id, request, state, cost_usd, cap_usd, steps, started_at, ended_at}]}`; run `state` is `running\|done\|stopped\|failed` (an over-budget Run is `stopped`, with the reason in its `stop` event). |
| `GET /api/runs/{run_id}/events` | `[trace…]` in order — exactly what was streamed live. |
| `GET /shots/{run}/{n}.jpg` | unchanged. |

Not in v1: renaming or deleting chats, search, attachments.

### Security (each is a test)

- Every `/api` and `/ws` request must carry a `Host` of `127.0.0.1:<port>` or `localhost:<port>` (blocks DNS rebinding).
- `POST` requires `Content-Type: application/json` and an allowed `Origin`; no CORS headers are ever sent.
- IDs are server-generated 32-hex strings and are validated before any lookup; screenshot paths are never built from user input.
- Model output is untrusted: the page renders markdown **without raw HTML**, allows only `http(s)` and `mailto` links, and sets `rel="noopener noreferrer"` on them.

### Placeholders (graduate when Approvals land, iteration B5)

`{"type": "question", ...}` and `{"type": "approval", ...}` frames, and page → server `{"type": "answer", ...}` / `{"type": "approve", "approval_id": "…", "yes": true}`. Shapes are decided in B5; the page ignores them until then.

## Fixtures

`web/fixtures/` holds recorded or hand-made runs in the v1 shape: a web run with screenshots, a Files run (invented paths only: **never** real paths from a Ledger), a refused action, a Stop, an over-budget stop, a Decline. The UI lane builds against a mock server that replays them; the Main lane's contract test validates them.

## Settled at sign-off (X1, 2026-10-07)

1. A chat's title is the first request cut to 60 characters (no model call).
2. `queued` is shown in the chat list and in `status`; that is enough for v1.
3. The cost footer leaves the reply text once the page reads `cost_usd` (at sync X2).
4. Also accepted: `cap_usd` on the status frame and on runs, and `url` and `title` on `shot` events.

Any change from here is a `contract` log entry and a version note in this file.

## Notes from U2b (2026-10-08): how the channel fills in what v1 left open

Behaviour only; no field is added or changed ([log](log/2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md)).

- **`status` between a message and its Run.** `state` is `running` as soon as a message is taken from the queue. `active` stays `null` until the Run's first event arrives (screening takes about a second), then carries the run id and `cap_usd`. A `status` frame is sent only when the queue or the active Run changes, not per event.
- **Queued messages.** Your message is echoed as a `message` frame at once, even when it has to wait. It is not saved until its turn, so `GET /api/conversations/{id}` adds it to the chat read back, and a chat whose first message is queued appears in the list with `state: "queued"`.
- **`POST /api/conversations`** answers `201` with `{id}`. The chat is not stored (and not in the list) until its first message is saved; until then `GET /api/conversations/{id}` answers `200` with an empty chat. `send` accepts a chat id that history knows or that this process issued, so after a restart an unused id is unknown.
- **Ids.** 32 lowercase hex, plus the literal `default` (the CLI's chat; a v0 page's messages go there). Anything else answers `404` before any lookup. `GET /api/runs/{id}/events` answers `404` for an unknown Run and for a Run with no events yet.
- **A message and its saved copy.** A reply's live frame carries the id and time of its saved copy. A user message's echo goes out before it is saved, so its id differs from the saved one; the page treats history as the record (it keeps a live message only if it is newer than anything history has).
- **A Run left open by a crash** reads `failed` when a chat is read back, unless it is the live Run.
- **Old pages.** For one release a v0 page's `{"text": …}` and `{"stop": true}` are still accepted (into `default`); v0 frames are no longer sent.
- **Client frames** are validated by `contract.py`: a stray field, a missing `text`, a text over 20 000 characters, or an unknown chat is ignored (no error frame).

## Live view (added 2026-10-08, additive)

The User sees the Assistant's headless browser while it works ([decision](log/2026-10-08-a-live-headless-browser-view-replaces-the-screenshot-only-vi.md), [contract entry](log/2026-10-08-live-view-get-live-run-id-and-the-browser-on-frame-seam.md)). View-only: nothing the page does reaches the browser.

| Route | Returns |
|---|---|
| `GET /live/{run_id}` | `multipart/x-mixed-replace; boundary=frame`: a stream of `image/jpeg` parts. The newest frame at once, then each new one; the stream ends when the Run ends. `404` for an id that is not 32 hex characters, or a Run that is not active. Same Host and Origin guard as every route; no CORS header. |

- **In the page:** `<img src="/live/<run_id>">` while the Run is running and has a Browser step; when the stream ends (or on `404`) the page shows the Run's last `shot` instead. Thumbnails and the viewer for saved screenshots (`shot` events, `/shots/...`) are unchanged.
- **Behind it:** `Browser(shots=..., on_frame=cb)` calls `cb(run_id: str, jpeg: bytes)` (synchronous, non-blocking, at most four times a second per Run, JPEG no larger than the 1000 by 700 viewport). `app.py` passes the channel's `live_frame(run_id, jpeg)` when it has one. The channel keeps only the newest frame per active Run and stores nothing: the `shot` events stay the record.
- **What the channel does** (U3, [log](log/2026-10-08-live-view-the-channel-streams-the-newest-frame-of-the-active.md)): the stream starts with the newest frame (older ones are never replayed), sends each later one, skips frames a slow client missed, and ends with the closing boundary `--frame--` when the Run ends or the server stops. Each part has `Content-Type: image/jpeg` and a `Content-Length`; the response has `Cache-Control: no-store`. A frame is accepted only if it is bytes starting with the JPEG marker, at most 1 000 000 bytes, and for the Run that is active now; anything else is dropped. A client that goes away is noticed within about a second and leaves nothing behind.
