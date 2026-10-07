# 0006 — SQLite for run state and the Ledger; Markdown for Memory

Status: accepted · 2026-10-06

Tasks, Runs, Checkpoints, Questions, Approvals, Approved sites and the Ledger live in one SQLite file (standard library, no server). At-most-once Consequential Actions need "intend this Action" and the Checkpoint written in one transaction before the browser acts; separate JSONL files can't do that atomically, and a crash between them would let an Action repeat. Memory stays as Markdown files because the User reads and edits them. Considered: JSONL everywhere (simpler, not atomic) and Postgres (a server for one user).

**Amended 2026-10-07.** All SQL lives in one internal Store module that Ledger and Runner both call, so a later port touches one file. Every table carries `user_id` from the start. Columns use real types, with no reliance on SQLite's loose typing or `rowid`. At-most-once for Consequential Actions rests on a unique constraint over (run, step, action), not on timing — SQLite's single writer would hide a race that Postgres exposes. The trigger for Postgres is not "the app got serious" but a second machine or many Users writing; the same tests then run against both databases and the storage seam becomes real. Expect a day or two of porting: placeholder syntax, timestamp and JSON types, upserts, locking.
