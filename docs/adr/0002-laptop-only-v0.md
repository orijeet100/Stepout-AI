# 0002 — V0 runs on the laptop only; no Docker

Date: 2026-10-06 · Status: accepted · Amended 2026-10-07: laptop-file tasks arrive in V0 as a local tool (S8) — see [0008](0008-laptop-files-grants.md)

**Decision.** V0 is one Python process on the owner's laptop. No always-on hub, cloud browser, containers, webhook channels, email, or credentials. Browser tasks use a fresh isolated Playwright context (no host profile, temp downloads). Messages sent while the laptop is off wait on Telegram (up to 24 h) and are processed on wake; any older than 30 min get "still want this?".

**Why.** Docker Desktop was installed but not running; a container adds a daemon and little protection while the agent has no file tool. The real V0 risks — prompt injection and bad actions — are handled by the gate. One extra hole is closed in the gate: a browser can open `file://` and local addresses, so navigation is limited to http(s) on public hosts.

**Revisit when.** V1 adds the cloud worker (reproducible image, clean state per task) or a server-side brain that reaches the laptop's files through an outward-connecting helper ([0007](0007-brain-and-hands.md)).
