---
date: 2026-10-08
kind: decision
lane: both
status: accepted
title: tests/test_web_channel.py belongs to the UI lane
tags: [ownership,tests]
refs: [scripts/owners.py, docs/plan/README.md, docs/log/2026-10-08-tests-test-web-channel-py-is-rewritten-by-the-ui-lane-it-tes.md, tests/test_owners.py]
---

**What.** `tests/test_web_channel.py` is owned by the UI lane: a rule in `scripts/owners.py` and a mention in the plan's ownership table. A test in `tests/test_owners.py` pins it (the UI lane may change it, the Main lane may not). Everything else under `tests/` stays Main's.

**Why.** The file tests one thing, `src/stepout/channels/web.py`, which the UI lane owns, and U2b had to rewrite it for contract v1. The plan told the UI lane to write the channel's tests (`ui-worktree.md`, U2b step 3) but gave it no path outside `web/` to put them, and `testpaths = ["tests"]` is what keeps them in the Main suite that must stay green. The UI lane flagged the clash itself rather than working around it ([its entry](2026-10-08-tests-test-web-channel-py-is-rewritten-by-the-ui-lane-it-tes.md)). The merge agent's ownership check was red on this one path only.

**Alternatives.** Leave the check red and accept it at each merge: it trains everyone to ignore a red check. Move the tests under `web/` and out of the Main suite: the shipped channel would then have no test in the suite the Main lane runs. Make the Main lane own and rewrite them: it would be writing contract tests for a file it may not edit.

**Evidence.** `python scripts/owners.py --lane ui claude/ui-ux-pro-max-skill-f679d5` now exits 0 (it exited 1 on this path); `tests/test_owners.py` has the new case. Decided by the merge agent under the User's delegation of the orchestration.
