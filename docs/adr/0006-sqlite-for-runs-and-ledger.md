# 0006 — SQLite for run state and the Ledger; Markdown for Memory

Status: accepted · 2026-10-06

Tasks, Runs, Checkpoints, Questions, Approvals, Approved sites and the Ledger live in one SQLite file (standard library, no server). At-most-once Consequential Actions need "intend this Action" and the Checkpoint written in one transaction before the browser acts; separate JSONL files can't do that atomically, and a crash between them would let an Action repeat. Memory stays as Markdown files because the User reads and edits them. Considered: JSONL everywhere (simpler, not atomic) and Postgres (a server for one user).
