---
date: 2026-10-08
kind: note
lane: ui
status: accepted
title: Restored LF line endings my Python edits had changed to CRLF
tags: [hygiene,line-endings]
refs: [docs/STATUS.md, src/stepout/channels/web.py, web/src]
---

**What.** Eleven files this lane touched had LF endings on `main` and CRLF in this branch: `docs/STATUS.md`, `channels/web.py`, `web/e2e/test_run_view.py`, and eight files in `web/src`. They are back to LF. No content changed.

**Why.** My scripted edits read a file in Python text mode and wrote it back, and on Windows that writes CRLF. Every file I edited that way changed all of its lines, so `git diff main` showed whole files rewritten (and the shared `docs/STATUS.md` would have conflicted with Main's edits of its own section). The repo has no single convention (many files on `main` are CRLF, many LF), so the rule I follow is: a file keeps the style it has on `main`; a new file is LF.

**Alternatives.** Adding a `.gitattributes` or setting `core.autocrlf` (repo-wide settings, Main's call). Leaving it (noisy diffs and avoidable merge conflicts).

**Evidence.** `git diff --stat main -- docs/STATUS.md` went from the whole file to one paragraph. A check of every changed file's endings against `main`'s now reports none to fix. `npm test` 60 passed; build and lint clean; `tests/test_web_channel.py` 18 passed. From here on edits to existing files go through exact string replacement, not a read-modify-write in text mode.
