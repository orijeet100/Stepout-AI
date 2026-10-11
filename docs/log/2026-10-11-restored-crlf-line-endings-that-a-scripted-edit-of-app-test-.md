---
date: 2026-10-11
kind: note
lane: ui
status: accepted
title: "Restored CRLF line endings that a scripted edit of App.test.tsx had changed to LF"
tags: [housekeeping]
refs: [web/src/App.test.tsx, web/mock/server.py, web/mock/test_server.py]
---

**What.** `web/src/App.test.tsx` is stored with CRLF line endings; a scripted edit (the sidebar-fold test and an assertion about suggestions) rewrote it with LF, which made a 600-line change out of a 14-line one in the branch diff. The file is back to CRLF, so the diff shows only the two additions. `web/mock/server.py` and `web/mock/test_server.py` (also CRLF) were restored the same way earlier in the branch. No behaviour change.

**Why.** Reviewable diffs; the merge agent reads `git diff main..ui-enhancements`. Same cause and fix as [the entry of 2026-10-08](2026-10-08-restored-lf-line-endings-my-python-edits-had-changed-to-crlf.md) in the other direction.

**Evidence.** `git diff --stat main..HEAD -- web/src/App.test.tsx` is 14 added lines (two tests' worth); `npm test` 151 passed.
