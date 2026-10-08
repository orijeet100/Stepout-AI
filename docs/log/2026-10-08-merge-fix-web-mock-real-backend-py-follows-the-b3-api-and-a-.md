---
date: 2026-10-08
kind: change
lane: both
status: accepted
title: Merge fix: web/mock/real_backend.py follows the B3 API, and a test guards it
tags: [merge,demo,b3]
refs: [web/mock/real_backend.py, web/mock/test_real_backend.py, src/stepout/intake.py, src/stepout/runner.py, src/stepout/screening.py]
---

**What.** `web/mock/real_backend.py` (the UI lane's free demo: the real channel, database and history with a scripted model) was written against the pre-B3 API and failed on the merged tree with `TypeError: DemoRunner.submit() got an unexpected keyword argument 'screening_cost'`. It now follows B3: `DemoRunner.submit(task, previous=(), screening_cost=0.0)` passes both on, `Intake` gets a `DemoScreener` (a scripted stand-in for the Haiku front door: payments and invoices are declined, a greeting is answered as chat, a message starting "and " links the chat's last exchange) plus `history.exchanges`, and the model's old "no tools means Intake's routing question" branch is gone. New `web/mock/test_real_backend.py` starts the helper on a free port and checks one answer, one decline and one follow-up over the v1 protocol; run it with the other mock tests (`python -m pytest web/mock -q`).

**Why.** The merge agent found the break at sync 3. The UI lane could not have fixed it in its own branch: the B3 API exists only on the Main lane's branch and in the integration branch, and lanes take new work only from `main`. It is a break that exists only when both sides are combined, so the merge agent fixed it where both sides are visible (a narrow exception to "the merge agent only merges", for a change under 25 lines in a file whose lane is idle). The UI lane's STATUS tells people to run this helper; it now works again.

**Alternatives.** Hand it back to the UI lane: it would first have to merge the Main lane's branch, which the plan forbids between syncs. Delete the helper: it is the only free way to see the whole merged flow.

**Evidence.** The new test fails on the old file and passes on the new one; `python -m pytest web/mock -q`: 10 passed. Files: `web/mock/real_backend.py` (+19 -5), `web/mock/test_real_backend.py` (new). The UI lane picks the change up at its next `git merge main`.
