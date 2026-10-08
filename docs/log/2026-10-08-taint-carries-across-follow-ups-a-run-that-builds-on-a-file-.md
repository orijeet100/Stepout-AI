---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Taint carries across follow-ups: a Run that builds on a file-reading answer starts with the web closed
tags: [reader, taint, safety, history]
refs: [docs/plan/v0-finish.md, src/stepout/runner.py, src/stepout/history.py, src/stepout/ledger.py, src/stepout/migrations/0006_runs_tainted.sql, tests/test_taint_followups.py]
---

**What.** Taint (the web is closed once a file's text has been read, [strict taint](2026-10-08-strict-taint-the-web-closes-after-a-file-is-read.md)) now survives from one message to the next in a chat.
- A Run saves why it was tainted: `runs.tainted` (migration 0006; `Ledger.end_run(..., tainted)`, written in the same `finally` as the outcome).
- `history.exchanges` sets `Exchange.tainted` from it (it was always False).
- `Runner.submit` taints a Run before its first step if any Exchange it is given (`previous`) is tainted. The Gate's message to the model says why: "an earlier answer it builds on (#1) used the contents of your files". It is transitive: a follow-up that built on a tainted answer is itself tainted, so the one after it is too.
- The block of Previous exchanges marks a tainted one ("this answer used the contents of your files; the web is closed for any task that builds on it") and the Orchestrator prompt says to plan no web steps then, so it does not spend steps on refused ones.

**What is linked.** Only what the front door links, as before: the Exchanges named in `related`, or the last three when the front door cannot answer (fail-open). A new task the front door links to nothing is not tainted, whatever came before it in the chat. Taint stops at the chat: Exchanges are per conversation.

**Why.** A file can carry instructions; the web is the way out. Without this, "now open the company's site" typed after "summarize my resume" was a Run with a clean slate and a reply in front of it that quoted the file.

**Strict on purpose.** V0 does not relax this to "sites the User named in the request" (FR45, ADR 0010 point 8, the plan's done-when 5). It is a closed web, not a list, because naming a site is itself something an injected line can imitate and a list needs a parser we would then have to defend; the demos need nothing from the web after a read (Demo B reads the web first). If a real task needs it, the relaxation is one rule in `gate.check`. `docs/requirements.md` FR45 and `docs/architecture.md` now say what is built; ADR 0010 is left as the record of the original intent. The plan file `docs/plan/v0-finish.md` (done-when 5) still says "only sites the User named": the merge agent owns it.

**Alternatives.** A new Ledger event kind ("taint") instead of a column: the page's contract lists event kinds and an unknown one is a risk for the UI lane; a column is invisible to it and is what `history` needs (one query). Computing taint from `read_text` step events at read time: it would need to know which reads returned content, which is the capability's decision (an empty or refused read taints nothing) and is already recorded as the Run's state.

**Evidence.** `tests/test_taint_followups.py` (5): a Run given a tainted Exchange cannot browse (the page is never opened, web search is not offered, the refusal names the earlier answer); one given untainted Exchanges can; through the real app loop and a restart-style reopened Store, over four messages (read; follow-up; unlinked new task; follow-up of the follow-up) the Exchanges read `[tainted, tainted, clean, tainted]`, `runs.tainted` agrees, and only the unlinked task reached the browser; the fail-open fallback carries taint too. Mutation-checked: dropping the inheritance, not saving it, not reading it back, and not marking the block each fail a test. Offline suite 360 passed. Files: `src/stepout/{runner,history,ledger,domain,roles}.py`, `src/stepout/migrations/0006_runs_tainted.sql`, `src/stepout/gate.py` (comment), docs.
