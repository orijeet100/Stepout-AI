# Roadmap — V0

Date: 2026-10-07 · Language: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md) · Design: [`architecture.md`](architecture.md)

```
S0 ─► S1 ─► S1b ─► S2 ─► S3 ─┬─► S4 (Telegram) ─┬─► S6 ─► S7 ─► S8 (Files) ─► S9 (React page) ─► S10 (mem0)
                             └─► S5 (Memory) ───┘                      └──► S11 (Organize, V0.5)
```
S4 and S5 don't depend on each other. Everything else is in order. S11 can start once S8 is green; it is V0.5, after V0 is done.

Each slice: a short branch (`slice/NN-name`), interface tests green, a demo that works, a result in `docs/results/`, docs updated in the same commit, tag on merge. Aim for 2–3 days. Don't start a slice until the previous demo works.

| S | Builds (modules · adapters) | Tested through | You'll learn | Watch out for | Demo |
|---|---|---|---|---|---|
| **0** | Docs, glossaries, ADRs | — | domain language, seams | — | you sign off |
| **1** | domain types (Actions and Results as plain data) · Gate `screen` · Intake (Answer and Lookup Routes, commands) · Runner without a browser · Store · Model port + provider adapter + scripted model · Fetcher · Ledger · CLI Channel · app | `test_gate`, `test_intake`, `test_runner`, `test_app`; serialization round-trip | tool calling, the agent loop, structured output, cost accounting | search choice; model IDs and prices | "What's the weather?" answered by fetch with cost shown; "pay this invoice" Declined |
| **1b** | Roles: the Runner loop parameterized by a Role table · Orchestrator (no hands; `delegate`, `ask_user`, `answer`) + Direct · `Finding` (Untrusted) · one shared Budget, Taint and Ledger tree (Role + parent on every event) | `test_runner` with the scripted model: delegation, the shared Budget cap, a Finding that can't write Memory, Role-stack serialization | multi-agent as one loop; context isolation; least privilege | orchestration eating the $0.50 cap; specialists that delegate; what a Delegate carries | "What's the weather in Tokyo?" → the Orchestrator Delegates to Direct; the Ledger shows the tree and one total cost |
| **2** | Browser (Playwright, network policy) · Browser Role · Gate `check` (Risk, navigation) · Simulated web v1 (shop, forms, Receipts) | `test_gate` table, `test_runner` on the Simulated web | browser automation, page views, network interception | page-view format (spike); Chromium sandbox on Windows | research Task on the simulated shop with evidence; `file://` and `localhost` blocked |
| **3** | Runner: Questions, Approvals, Checkpoints, `recover()`, Uncertain, queue · Intake: Answers and Approvals · Approved sites | `test_runner` pause / resume / kill; `test_gate` Approval matching and expiry | durable state machines, at-most-once, idempotency | deciding when a click is Consequential | missing info → Question → Resume; Approval with fields → Receipt; kill mid-Run → resumes |
| **4** | Telegram Channel (aiogram): allowlist, buttons, photos, `/status`, Stale | adapter test with recorded payloads; a real phone run | long polling, chat UX, duplicate delivery | message length and formatting limits | S1–S3 demos from your phone |
| **5** | Memory (rules + Markdown store): `recall` / `remember` / `forget`, Pinned, Note expiry, redaction · Corrections | `test_memory`; `test_runner` (Recollection used); `test_intake` (Correction) | memory design, write rules, PII redaction | recall quality without embeddings | a fact given once is used next time; "that's wrong…" reopens and redoes |
| **6** | Evaluation: Golden tasks and Twins, Simulated user, harness, Conditions (Memory on/off; one loop vs orchestrated) | the harness and its report | eval design, controls, variance | spend (below); flaky Trials | **Baseline** table; Thresholds fixed |
| **7** | Security cases: Poisoned Variants, Blockers, Memory poisoning · hardening | the security suite | prompt injection, defence in depth | a green suite that is too small | zero Actions you didn't approve; zero Memory from Untrusted content |
| **8** | **Files** (Grants, Off-limits, `find` / `list` / `stat` / `read`, PDF text, secret screening, read Budget) · Files Role (read-only) · Gate rules for files and Taint · upload from a Grant · remembered locations in the Persona · Simulated folder | `test_files` path table, `test_gate`, `test_runner` | filesystem safety on Windows, PDF extraction, taint tracking | Windows path edge cases; PDF library licence; exfiltration through URLs after a read | "How many PDFs in `Resume`?" with no contents sent to the model; "Summarize the newest PDF" refused in `metadata`, works in `read`; "Upload my resume to this form" finds it itself, with an Approval |
| **9** | Web Channel: React + Vite + TypeScript page in `web/`, served by `channels/web.py`; view and edit `persona.md` | adapter test + manual | React over a WebSocket | sliding into a "product UI"; adding sign-in early | the same flows in a browser on home Wi-Fi |
| **10** | mem0 store behind Memory's internal seam · write-up | Evaluation rerun under both stores | comparing memory systems honestly | mem0's own model calls add cost | table: files vs mem0 — Interventions and cost |
| **11** *(V0.5)* | Files `organize`: Plan → Approval → apply → Undo journal, `/undo`, per-Run cap | `test_files`, `test_runner`, a Simulated folder | safe bulk change, reversibility | silent overwrites; a Plan that hides how many files move | organize `Downloads` by type with a Plan, Approval, then `/undo` restores everything |

**V0 is done** when S1–S9 and S1b are green, all 17 acceptance scenarios in [`requirements.md`](requirements.md) pass, and the S6 Thresholds are met. S10 follows.

**Why Files comes before the web page:** it is new capability, while the web page duplicates what Telegram already does. It comes after S7 because reading personal files is the first point where a hostile page could otherwise reach them — the defences must be proven first.

## Evaluation spend — estimate before S6

Trials = Golden tasks × Attempts × Conditions × repeats. A modest matrix: 6 × 5 × 2 × 2 = **120 Trials**. At roughly $0.05–$0.25 per Trial (a guess — replace it with the real average from the S1–S5 Ledger) that is **$6–$30 per full evaluation**, which can exceed the $25 monthly Budget. Decide in S6: a separate evaluation allowance, or a smaller matrix. The one-loop-vs-orchestrated Condition multiplies the matrix again — run it on a subset. Files Golden tasks (S8) run on a Simulated folder and need no browser, so they are cheap.

## Scope traps — what would blow this up

- Sign-in, hosting or multiple Users before V1. The React page is localhost / home Wi-Fi only.
- A plugin system or registry for Channels — a few adapters behind one small interface is enough.
- Embeddings or a vector database before S10 proves files fall short.
- A generic "agent framework" inside the repo — the Runner is one module for one job.
- Supporting every site. If a site blocks automation, the Outcome is Blocked and that's fine.
- Letting the model or the chat edit Grants, or shrinking Off-limits "just for this task".
- Organizing before the Undo journal exists.
- More than the four Roles, delegation deeper than one level, or a specialist that talks to the User. Computer use (driving the desktop) is not a Role in V0.
- Docker, a cloud server, credentials, email, scheduled Tasks — all V1.
- Perfect classification of Consequential clicks — unknown → Ask is the safety net.

## Parked for V1

Always-on server; cloud browser with a container per Task; a laptop helper so a cloud brain can reach your files; email as forward-to-agent; SMS, WhatsApp and voice; a hosted React app with sign-in from a provider, Postgres and multiple Users; credentials entered through a web form (never in chat); remote takeover; scheduled Tasks; computer use, nested delegation and more Roles; a named catalog of reusable Notes.
