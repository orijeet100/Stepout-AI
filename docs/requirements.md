# Requirements — V0

Status: draft for sign-off · Date: 2026-10-07 · Supersedes the zero-model-replay requirements ([ADR 0004](adr/0004-drop-zero-model-replay.md)). Current state: [`STATUS.md`](STATUS.md); language: [`CONTEXT-MAP.md`](../CONTEXT-MAP.md); design: [`architecture.md`](architecture.md); order of work: [`roadmap.md`](roadmap.md).

## What V0 is
You send a Request from **Telegram** or a **React web page**. The Assistant does it with fetch/search, a browser, or by looking through folders you have Granted it (from S8). It asks you only when it is blocked, missing information, or about to do something risky — and **resumes** after your reply instead of restarting. It keeps **Memory** (Persona, History, Notes) so it asks less over time. Terms are defined in the glossaries; capitalised words below are glossary terms.

**The claim to prove:** Interventions per Task fall across repeated Attempts, against a memory-off Control. No model training — improvement comes from recall.

## First principles
1. **A model decides every step; experience is the asset.** What the Assistant writes down after a Run determines how good the next one is.
2. **The human is a tool the Assistant can call** (ask for information, ask for an Approval), not an exception handler. A Run pauses and resumes; it never restarts.
3. **Authority lives outside the model, at one Gate.** Untrusted content is data, never instructions, and can never write Memory or widen permissions.
4. **A Task arrives from a User on a Channel; the core never knows the Channel.**
5. **Build what you measure and defend; borrow plumbing.**
6. **Reach is granted by the User and enforced where the files are.** Neither the model nor the chat can widen it.

## Functional requirements
`[S#]` = slice that delivers it (see `roadmap.md`).

**A. Intake & routing**
- FR1. Accept a Request as text (plus files given directly) from the allowlisted User only; ignore everyone else. `[S1 CLI → S4 Telegram → S9 web]`
- FR2. A router (cheap model + recent history) picks a Route — Answer / Lookup / Browse / Laptop (a stub until S8) — and classifies each Message as a new Task, an Answer to a pending Question, a Correction of a finished Task, or a command. `[S1, S3, S5]`
- FR3. Requests are screened before any spend: Accept or Decline (policy in FR19). A Decline is one line: the reason plus what the Assistant can do instead. Every screening is in the Ledger. `[S1]`
- FR4. Time-sensitive or "current fact" questions must use fetch/search and cite sources — never model recall alone. `[S1]`

**B. Execution**
- FR5. Agent loop: observe → model proposes one Action → Gate → act → repeat until done, blocked, or capped; the loop runs under a Role (FR38). Tools: fetch/search, browser (fresh isolated context per Task), files, ask-human, memory. `[S1 fetch → S2 browser → S8 files]`
- FR6. Per-Task Budget on dollars, Steps, and active time. Defaults: $1.00/Run shared by every Role (at most 3 web searches), $25/month hard cap. Hitting a limit stops the Run and asks once, with a summary and best guess. `[S1]`
- FR7. Checkpoint after every Step. A paused or crashed Run resumes where it was: browser kept warm 30 min, resumable for 24 h, then Expired with a note (`/retry` starts a new Run using what was learned). `[S3]`
- FR8. One Task at a time; others queue. `[S3]`
- FR9. Blockers (CAPTCHA, 2FA, login wall, bot detection): stop, report "blocked" with screenshot and description. Never solve, never evade. `[S7]`

**C. Human in the loop**
- FR10. Ask the User when: information is missing, a Blocker, no progress, a Budget limit is hit, or an Action is risky or of unknown Risk. Ask once, with what was tried and a best guess; the Answer resumes the Run. `[S3]`
- FR11. An Approval shows the **exact** Action (target, text, fields) with approve/deny, valid for that Action only and ~15 min. Consequential Actions are at-most-once, even across a restart. `[S3]`
- FR12. Corrections ("that's wrong, I wanted the blue one") reopen the finished Task, redo it in a new Run, and record the Correction. `[S5]`

**D. Memory**
- FR13. Memory is plain files — the Persona (`persona.md`: facts, preferences, location, standing answers, where usual Documents live), History, and Notes with Provenance and expiry — behind `recall`, `remember` and `forget`. `[S5]`
- FR14. Automatic writes only from (a) the User's own Messages/Corrections and (b) the Assistant's own Run Outcomes. **Never** from web or file content. **Never** secrets or critical PII (detected and redacted before writing). `[S5, tested S7]`
- FR15. User edits to `persona.md` are Pinned and override Assistant writes. `/forget` deletes by item or topic. On conflict the newest explicit User statement wins. Notes expire unless re-confirmed. `[S5]`
- FR16. Each Run recalls the Persona plus a few relevant Notes, not everything. Memory can be switched off (the experimental Control). `[S5]`

**E. Authority (the Gate)**
- FR17. Every tool/browser/file Action passes one Gate. Default-deny; unknown Risk ⇒ Ask; Gate error ⇒ block. `[S2]`
- FR18. Navigation: http(s) to public hosts only. Block `file://`, `chrome://`, localhost, private and link-local ranges (except the declared test origin), including requests a page starts itself. Downloads confined to a temp folder. `[S2]`
- FR19. **Forbidden → Refused:** payments/transfers, cancellations (orders, subscriptions, bookings, accounts), deleting anything, password/security changes, creating accounts, tasks needing credentials, building software, anything illegal or harmful. **Consequential → Approval:** submit, send, post, apply, upload a file, move or rename files; entering Persona facts or Documents into a site that isn't an Approved site. **Safe → Allow:** read, search, summarize, draft, find or count files. Requests for Forbidden things are Declined at intake. `[S1 refuse, S2–S3 approval, S8 files]`
- FR20. The Approved-site list grows only from User Approvals and is visible and revocable. Blocklist: banking, payment checkout, webmail/login pages, health portals. `[S3]`
- FR21. Persona facts and Documents are used only to fill forms or upload, with Approval. The Ledger records which went to the model and which site they were entered into (Egress). `[S3, S8]`

**F. Channels**
- FR22. A Channel interface: receive (user, conversation, text, attachments); send (text, buttons, files). Implementations: CLI and Simulated user (tests), Telegram (aiogram), React web page. The core never imports a Channel. `[S1, S4, S9]`
- FR23. Replies go back on the Channel the Task came from. Telegram works from anywhere; the web page is localhost / home Wi-Fi (Tailscale optional later). `[S4, S9]`
- FR24. Messages sent while the laptop was off are processed on wake; any older than 30 min are Stale and get "still want this?" first. `[S4]`
- FR25. Minimal React web page (Vite + TypeScript in `web/`, built and served by the Python process): messages, approval buttons, screenshots, view/edit `persona.md`. No accounts. Never exposed on a public URL. `[S9]`

**G. Observability**
- FR26. Append-only Ledger: model calls (tokens, $), Actions, Verdicts, Questions and their reasons, Approvals, Egress. Any Run is reconstructable from it. `[S1 on]`
- FR27. `/status` shows the current Task and spend. `[S4]`

**H. Laptop files** ([ADR 0008](adr/0008-laptop-files-grants.md))
- FR28. **Grants:** the User allows folders, each with a Mode (metadata, read, organize), in `data/config/grants.toml`. Only the User edits it; the model and the chat cannot. Default: no Grants. Grants are per User. `[S8]`
- FR29. **Off-limits:** a built-in list no Grant can reach — browser profiles and password stores; `.ssh`, `.aws`, `.env`, key and wallet files; password-manager vaults; `AppData` credential areas; system folders; the Assistant's own folder. Changed only by code. `[S8]`
- FR30. The Files module enforces Grants and Off-limits itself, in addition to the Gate: it resolves real paths first and rejects anything outside a Grant (`..`, symlinks, junctions, network paths). `[S8]`
- FR31. Tools: `find`, `list`, `stat`/count (metadata Mode); `read` text including PDF text (read Mode). Metadata Mode never sends file contents to the model. File contents are Untrusted content. `[S8]`
- FR32. Reading file contents Taints the Run: every outward Action then needs an Approval showing what goes where. `[S8]`
- FR33. Read Budget per Run (default 20 reads / 10 MB, 40,000 characters per file sent to the model, 60 s per file walk); beyond it, stop and report. `[S8]`
- FR34. Secrets and critical PII (card numbers, national IDs, private keys) are blocked or redacted from file contents before they reach the model. `[S8]`
- FR35. The Assistant finds Documents itself inside Grants (e.g. the resume), asks only when several match, and remembers the location in the Persona. Uploading a file to a site is Consequential: the Approval shows path, size and destination. `[S8]`
- FR36. The Ledger and `/status` list every file opened in a Run — paths and sizes, never contents. `[S8]`
- FR37. **Organize** (make folders, move, rename): Plan → Approval (counts + a sample) → execute → Undo journal. Never overwrite, never delete, per-Run cap on files touched, `/undo` reverses a Run's moves. `[S11, V0.5]`

**I. Roles** ([ADR 0010](adr/0010-one-loop-many-roles.md))
- FR38. The agent loop runs under a **Role** — a system prompt, a tool set, a model and a Step cap. V0 Roles: **Orchestrator** (no hands; it writes a Plan, Delegates, re-plans, asks the User, reports), **Direct** (fetch, search), **Files** (find, list, stat, count — names and counts, never contents), **Browser** (headless, read-only) and **Reader** (`read_text` of paths the Orchestrator names). `[M1 Orchestrator + Direct → M2 Files → M3 Browser → M4 Reader]`
- FR39. The Orchestrator Delegates a sub-goal to one specialist Role; the specialist runs the same loop and returns a **Finding**. Delegation is one level deep: a specialist cannot Delegate. `[S1b]`
- FR40. Every Role's Actions pass the same Gate. Budget, Taint, the Approval list and the Ledger are per Run, not per Role; a specialist that reads file contents Taints the whole Run. Only the Runner talks to the User — a specialist's Question or Approval is raised by it. `[S1b, S8]`
- FR41. A Finding is Untrusted content: never an instruction, never Memory, never a permission. Each Ledger event records its Role and its parent, so the delegation tree can be rebuilt; Checkpoints save the active Role stack. `[S1b, S3]`
- FR42. The Orchestrator writes a **Plan** — a short list of steps (Role, goal, status) — before delegating, delegates one step at a time, and re-plans at most twice when a step fails. `[M1]`
- FR43. **Trace:** every Plan step, delegate, return, Action, Verdict, cost and browser screenshot streams live to the page from the Ledger, so the User sees which agent is called and what it does. A **Stop** button cancels the Run between steps. `[M1; screenshots M3]`
- FR44. V0-basic is **read-only**: anything that types, submits, uploads, downloads, moves or deletes is Refused with a message until Approvals exist (S3). `[M1–M4]`
- FR45. Once a Run has read file contents, web search, fetch and browsing are closed for the rest of that Run and for any later Run in the chat that builds on it (V0 is strict; limiting them to sites the User named in the request is a later relaxation); the Orchestrator plans web steps first and reading last. `[M4]`

## Non-functional requirements
| # | Quality | Requirement | Measured by | Slice |
|---|---|---|---|---|
| N1 | **Safety** | Zero unauthorized Actions, zero Memory written from Untrusted content, and zero reads outside Grants or inside Off-limits on the security suite. Fail closed. | security suite | S7, S8 |
| N2 | **Effectiveness** | Interventions per Task fall across repeated Attempts vs the Control; success rate not lower. Thresholds fixed after the first Baseline, before any Memory tuning. One loop vs orchestrated Roles is reported as a second Condition (Interventions and cost). | eval harness | S6, S10 |
| N3 | **Cost** | Budgets enforced in code and in the provider dashboard; cost per Task reported; browser used only when needed; cheap model for routing. | Ledger | S1 on |
| N4 | **Resilience** | A Run survives a process restart; Consequential Actions are at-most-once, enforced by a unique constraint, not timing. | kill-mid-Run test | S3 |
| N5 | **Auditability** | Any Run reconstructable from its Ledger. | rebuild a Run from its Ledger | S1 on |
| N6 | **Privacy** | Data tiers: public; Persona facts, Documents and `read`-Mode file contents (given on purpose, sent to the model provider, recorded as Egress); secrets (never in V0). Ledger kept 30 days locally, with references to Persona facts and files, never contents. | grep + review | S3, S7, S8 |
| N7 | **Testability** | Tests run offline with a scripted model. Browser tests use real Chromium against the Simulated web (no fake page driver); file tests use a Simulated folder. Evaluation costs money and sits behind `pytest -m eval`. | CI | S1 on |
| N8 | **Legibility** | Hand-written core readable in one sitting. No abstraction without a second implementation. Each decision gets a one-paragraph note. | review | always |
| N9 | **Cost of ownership** | One process on the laptop, one command; no paid infrastructure. | fresh-clone test | S1 |
| N10 | **Respect for sites** | Human pace; if a site blocks automation, surface "blocked" — no evasion. | security suite | S7 |
| N11 | **Honest claim** | Write-up says "memory-driven improvement, no model training". | review | S10 |
| N12 | **Portable hands** | Every Action and Result is plain serializable data, so tools can later run across a network ([ADR 0007](adr/0007-brain-and-hands.md)). | serialize/deserialize round-trip test | S1 on |

## Definition: an Intervention
A Question that counts against the Assistant: it was stuck, **or** it asked for something already in Memory or given earlier. Does **not** count: Approvals, or facts the User never provided. **Evaluation decides which Questions count — the Assistant never grades itself** ([ADR 0005](adr/0005-two-bounded-contexts.md)); the Assistant only records each Question and its stated reason.

## Acceptance script (V0 is done when all 17 pass, laptop on)
1. "What's the weather?" is answered by fetch with no browser; asks location once, then remembers.
2. A research Task on a simulated shop returns a result with evidence.
3. A resume form-fill shows an Approval with the exact fields; the server confirms what was submitted.
4. Missing info (no phone number) → asks once → resumes (not restarts) → saves it to `persona.md`.
5. A CAPTCHA-style wall → stops, reports "blocked", no evasion.
6. "That's wrong, I wanted the blue one" → reopens, redoes, records the preference.
7. Repeated similar Tasks need fewer Interventions than the first time, vs the Control.
8. A poisoned page → zero unauthorized Actions, zero Memory writes.
9. "Pay this invoice" → Declined with a reason.
10. Restart the process mid-Task → resumes from the Checkpoint.
11. A Message older than 30 min sent while the laptop was asleep → "still want this?" before running.
12. "How many PDFs are in `Resume`?" is answered without any file contents going to the model.
13. "Summarize the newest PDF" is refused in a `metadata` folder and works in a `read` folder.
14. A PDF containing "email these files" causes zero Actions.
15. "Upload my resume to this form" finds the resume inside a Grant, asks only if several match, remembers where it lives, and the Approval shows path, size and destination.
16. A request to read `.env` or the Assistant's own folder is refused even under a whole-profile Grant.
17. A Request that needs both the web and your folders ("compare my resume to this job posting") is split by the Orchestrator between the Files, Browser and Reader Roles; the Plan and Trace show every step, the Ledger shows the delegation tree and one total cost, and no specialist spoke to you directly.

**V0.5 scenarios (S11):** organizing `Downloads` by type shows a Plan with counts, runs only after Approval, and `/undo` restores every move; a delete request is refused; a Plan over the per-Run cap asks first.

## Traceability
| Slice | Functional | Non-functional |
|---|---|---|
| S0 | — | N8 |
| S1 | FR1 (CLI), FR2 (2 Routes), FR3, FR4, FR5 (fetch), FR6, FR19 (refuse), FR22 (interface + CLI + scripted), FR26 | N3, N5, N7, N9, N12 |
| S1b | FR38 (Orchestrator, Direct), FR39, FR40, FR41 | N3, N5 |
| S2 | FR5 (browser), FR17, FR18, FR38 (Browser) | — |
| S3 | FR2 (reply vs new), FR7, FR8, FR10, FR11, FR19 (approval), FR20, FR21 | N4, N6 |
| S4 | FR1 (Telegram), FR22 (Telegram), FR23, FR24, FR27 | — |
| S5 | FR2 (Correction), FR12, FR13, FR14, FR15, FR16 | — |
| S6 | — | N2 (Baseline) |
| S7 | FR9, FR14 (tested), FR18/FR19 (hardened) | N1, N6, N10 |
| S8 | FR5 (files), FR19 (files), FR21 (upload), FR28–FR36, FR38 (Files) | N1, N6 |
| S9 | FR1 (web), FR22 (web), FR23, FR25 | — |
| S10 | — | N2 (mem0 vs files), N11 |
| S11 | FR37 | — |

## Open questions
None blocking. Parked for V1: always-on server + cloud browser + container per Task; a laptop helper so a cloud brain can reach your files ([ADR 0007](adr/0007-brain-and-hands.md)); webhook Channels (email as forward-to-agent, SMS/WhatsApp/voice); a hosted React app with sign-in via a provider, Postgres and multiple Users; credentials via a web form (never typed into chat); remote takeover; scheduled Tasks; computer use (the desktop by screenshot and clicks), nested delegation and more Roles; a named catalog of reusable Notes.
