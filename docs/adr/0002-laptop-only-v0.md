# 0002 — V0 runs on the laptop only; no Docker

Date: 2026-10-06 · Status: accepted

**Decision.** V0 is one Python process on the owner's laptop. No always-on hub, cloud browser, containers, webhook channels, email, or credentials. Browser tasks use a fresh isolated Playwright context (no host profile, temp downloads). Messages sent while the laptop is off wait on Telegram (up to 24 h) and are processed on wake; any older than 30 min get "still want this?".

**Why.** Docker Desktop was installed but not running; a container adds a daemon and little protection while the agent has no file tool. The real V0 risks — prompt injection and bad actions — are handled by the gate. One extra hole is closed in the gate: a browser can open `file://` and local addresses, so navigation is limited to http(s) on public hosts.

**Revisit when.** V1 adds laptop-file tasks (container mounts only the allowed folder) or the cloud worker (reproducible image, clean state per task).
