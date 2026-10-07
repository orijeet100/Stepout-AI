# Roadmap — V0

Date: 2026-10-06 · Language: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md) · Design: [`architecture.md`](architecture.md)

```
S0 ─► S1 ─► S2 ─► S3 ─┬─► S4 (Telegram) ─┬─► S6 ─► S7 ─► S8 ─► S9
                      └─► S5 (Memory) ───┘
```
S4 and S5 don't depend on each other. Everything else is in order.

Each slice: a short branch (`slice/NN-name`), interface tests green, a demo that works, a result in `docs/results/`, docs updated in the same commit, tag on merge. Aim for 2–3 days. Don't start a slice until the previous demo works.

| S | Builds (modules · adapters) | Tested through | You'll learn | Watch out for | Demo |
|---|---|---|---|---|---|
| **0** | Docs, glossaries, ADRs | — | domain language, seams | — | you sign off |
| **1** | domain types · Gate `screen` · Intake (Answer and Lookup routes, commands) · Runner without a browser · Model port + provider adapter + scripted model · Fetcher · Ledger · CLI Channel · app | `test_gate`, `test_intake`, `test_runner`, `test_app` | tool calling, the agent loop, structured output, cost accounting | search choice; model IDs and prices | "What's the weather?" answered by fetch with cost shown; "pay this invoice" Declined |
| **2** | Browser (Playwright, network policy) · Gate `check` (Risk, navigation) · Simulated web v1 (shop, forms, Receipts) | `test_gate` table, `test_runner` on the Simulated web | browser automation, page views, network interception | page-view format (spike); Chromium sandbox on Windows | research Task on the simulated shop with evidence; `file://` and `localhost` blocked |
| **3** | Runner: Questions, Approvals, Checkpoints, `recover()`, Uncertain, queue · Intake: Answers and Approvals · Approved sites | `test_runner` pause / resume / kill; `test_gate` Approval matching and expiry | durable state machines, at-most-once, idempotency | deciding when a click is Consequential | missing info → Question → Resume; Approval with fields → Receipt; kill mid-Run → resumes |
| **4** | Telegram Channel (aiogram): allowlist, buttons, photos, `/status`, Stale | adapter test with recorded payloads; a real phone run | long polling, chat UX, duplicate delivery | message length and formatting limits | S1–S3 demos from your phone |
| **5** | Memory (rules + Markdown store): `recall` / `remember` / `forget`, Pinned, Note expiry, redaction · Corrections | `test_memory`; `test_runner` (Recollection used); `test_intake` (Correction) | memory design, write rules, PII redaction | recall quality without embeddings | a fact given once is used next time; "that's wrong…" reopens and redoes |
| **6** | Evaluation: Golden tasks and Twins, Simulated user, harness, Conditions | the harness and its report | eval design, controls, variance | spend (below); flaky Trials | **Baseline** table; Thresholds fixed |
| **7** | Security cases: Poisoned Variants, Blockers, Memory poisoning · hardening | the security suite | prompt injection, defence in depth | a green suite that is too small | zero Actions you didn't approve; zero Memory from Untrusted content |
| **8** | Web Channel: one page + WebSocket; view and edit `persona.md` | adapter test + manual | a thin web front end | sliding into building a "product UI" | the same flows in a browser on home Wi-Fi |
| **9** | mem0 store behind Memory's internal seam · write-up | Evaluation rerun under both stores | comparing memory systems honestly | mem0's own model calls add cost | table: files vs mem0 — Interventions and cost |

**V0 is done** when S1–S8 are green, all 11 acceptance scenarios in [`requirements.md`](requirements.md) pass, and the S6 Thresholds are met.

## Evaluation spend — estimate before S6

Trials = Golden tasks × Attempts × Conditions × repeats. A modest matrix: 6 × 5 × 2 × 2 = **120 Trials**. At roughly $0.05–$0.25 per Trial (a guess — replace it with the real average from the S1–S5 Ledger) that is **$6–$30 per full evaluation**, which can exceed the $25 monthly Budget. Decide in S6: a separate evaluation allowance, or a smaller matrix.

## Scope traps — what would blow this up

- A "real" web UI before S8, or anything beyond one page.
- A plugin system or registry for Channels — three adapters behind one small interface is enough.
- Embeddings or a vector database before S9 proves files fall short.
- A generic "agent framework" inside the repo — the Runner is one module for one job.
- Supporting every site. If a site blocks automation, the Outcome is Blocked and that's fine.
- Docker, a cloud box, multiple users, credentials, email, scheduled Tasks — all V1.
- Perfect classification of Consequential clicks — unknown → Ask is the safety net.

## Parked for V1

Always-on hub; cloud browser with a container per Task; email as forward-to-agent; SMS, WhatsApp and voice; credentials entered through a web form (never in chat); remote takeover; scheduled Tasks; Laptop-route Tasks (a container that mounts only the allowed folder); multiple users; a named catalog of reusable Notes.
