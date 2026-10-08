---
date: 2026-10-08
kind: contract
lane: both
status: accepted
title: Live view: GET /live/{run_id} and the Browser on_frame seam
tags: [contract,live,browser]
refs: [docs/ui-contract.md, docs/log/2026-10-08-a-live-headless-browser-view-replaces-the-screenshot-only-vi.md, src/stepout/browser.py, src/stepout/channels/web.py, src/stepout/app.py]
---

**What.** Additive; no existing frame, field or route changes (contract rule 1). The full text is in [`../ui-contract.md`](../ui-contract.md) under "Live view".
1. **Route `GET /live/{run_id}`** (UI lane, `channels/web.py`): a `multipart/x-mixed-replace; boundary=frame` stream of `image/jpeg` parts. A browser shows it natively in `<img src="/live/<run_id>">`, so the page needs no frame parser. It sends the newest frame at once, then each new frame, and ends when the Run ends. It answers `404` for a malformed id or a Run that is not active. The same Host and Origin guard as every route; no CORS header.
2. **Seam `Browser(..., on_frame=cb)`** (Main lane, `browser.py`): `cb(run_id: str, jpeg: bytes) -> None`, synchronous and non-blocking, called at most four times a second per Run, only while the Run's page exists. Frames are JPEG, at most the existing 1000 by 700 viewport, quality about 50.
3. **Wiring** (Main lane, `app.py`): when the channel has a `live_frame(run_id, jpeg)` method, `app.py` passes it as `on_frame`. The CLI channel has none, so no frames are captured for it.
4. **Frames are not stored.** The channel keeps only the newest frame per active Run; nothing goes to the Ledger or the database. The recorded `shot` events (and `/shots/...`) are unchanged and remain the record.

**Why.** The live view is decided ([entry](2026-10-08-a-live-headless-browser-view-replaces-the-screenshot-only-vi.md)); this is the smallest interface both lanes can build against in parallel. `<img>` over MJPEG is the platform doing the work (no WebSocket frame type, no base64 on the control channel, no client parser), and a seam that is one callback keeps `browser.py` ignorant of the web.

**Alternatives.** Base64 JPEG in a new `/ws` frame: big payloads on the control socket, and a client decoder. A second WebSocket per Run: more state for the same result. Polling `/shots`: only as live as the last step.

**Evidence.** To be shown by the cycle that builds it: a Main-lane test of `on_frame` with real Chrome, a UI-lane test of the route (404s, Host/Origin, stream ends with the Run) and of the page, then the merge agent's live check on a real page.
