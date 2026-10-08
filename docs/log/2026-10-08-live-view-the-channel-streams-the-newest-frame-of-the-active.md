---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "Live view: the channel streams the newest frame of the active Run"
tags: [live,channel,security]
refs: [src/stepout/channels/web.py, tests/test_web_channel.py, docs/ui-contract.md, docs/log/2026-10-08-live-view-get-live-run-id-and-the-browser-on-frame-seam.md]
---

**What.** The UI-lane half of [the live-view contract](2026-10-08-live-view-get-live-run-id-and-the-browser-on-frame-seam.md). `WebChannel.live_frame(run_id, jpeg)` is the seam the Browser's `on_frame` will call (a plain synchronous function, quick, no await). `GET /live/{run_id}` answers `multipart/x-mixed-replace; boundary=frame` with `image/jpeg` parts: the newest frame at once (older ones are never replayed), then each new one (a slow client skips what it missed), and a closing boundary when the Run ends or the server stops. `404` for an id that is not 32 lowercase hex, and for a Run that is not the active one. It goes through the same guard as every route (Host, Origin) and sends no CORS header. The streaming lives in a small `LiveView` class that keeps **one frame per active Run and nothing else**: nothing in the Ledger, the database or on disk; a Run's frame and its streams go the moment the Run ends (one `_set_run` in the channel does it for every way a Run can end), and `stop()` ends open streams instead of waiting for them. A frame is accepted only if it is bytes, starts with the JPEG marker, is at most 1 000 000 bytes, and is for the active Run; anything else is dropped. A client that goes away is noticed within a second (aiohttp does not cancel a handler when the client leaves) and its stream is removed.

**Why.** Item 2 of `docs/plan/v0-finish.md`, built so the page can use a plain `<img src="/live/<run_id>">`: the browser parses the stream, the page needs no frame decoder. Nothing is stored, so the live view adds no new place for what the Browser saw to leak from, and `shot` events stay the record.

**Alternatives.** Base64 frames over `/ws` (large payloads on the control socket and a decoder in the page). Keeping a ring of recent frames (a replay feature nobody asked for, and a growing store). A watchdog thread for departed clients instead of the one-second check inside the stream.

**Evidence.** `tests/test_web_channel.py`: 26 passed, stable over repeated runs. The live tests cover 404 for malformed ids and for a Run that is unknown, a different active Run, or ended; the Host and Origin guard and no CORS header on 200, 404 and 403; newest frame first, then each new one, and a frame for another Run never reaching the stream; the stream ending with the Run (closing boundary, no frame and no watcher left); a client that leaves mid-stream leaving nothing behind; 200 frames fed leaving exactly one; junk (not JPEG, empty, oversized, not bytes, wrong Run) ignored; `stop()` ending an open stream; and `live_frame` being a plain function. Mutation checks: with each guarantee switched off (the 404 for an inactive Run, ending streams with the Run, noticing a departed client, JPEG-only, active-Run-only, size cap, `stop()` closing streams, not resending a frame) its test fails or hangs. **Not verified:** a real Browser feeding it (that is the Main lane's `on_frame` and the merge agent's live check), and the page showing it (C2).
