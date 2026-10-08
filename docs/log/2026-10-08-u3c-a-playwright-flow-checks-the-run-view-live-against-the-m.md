---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: U3c: a Playwright flow checks the run view live against the mock
tags: [u3,e2e,testing]
refs: [web/e2e/conftest.py, web/e2e/test_run_view.py, docs/plan/ui-worktree.md]
---

**What.** `web/e2e/` runs the installed Chrome (like the Browser agent) against a production build of the page behind `vite preview` and the mock backend, on free ports, started and stopped by the test session (`python -m pytest web/e2e -q`; the Main lane's pytest only collects `tests/`, so the two do not mix). Four flows: (1) a Run updates live (open, "Working…", Stop, Budget meter with `aria-valuemax` 1, a plan step turning done while we watch), then ends collapsed as `N steps · $cost · S s`, and **those numbers equal what the page's own API returns for the Run's events** (step count, summed cost rounded to cents, seconds from first to last event); expanding shows the plan and the steps; (2) Stop ends a Run and the block reads "Stopped by you · …"; (3) a request the Gate declines starts no Run and shows the note; (4) a message sent while a Run is busy carries the Queued tag and the header pill, then runs. Every test also fails on any console error. Screenshots go to pytest's tmp dir, never to git.

**Why.** U3's done-when: "a Playwright flow shows the run view updating live against the mock; the summary matches the numbers in the fixture."

**Alternatives.** The dev server instead of a build (not what ships; the preview proxy is the production-like path and also exercised the WebSocket proxy). Playwright's own test runner and its Node package (a second toolchain; the Python API is already a project dependency).

**Evidence.** `python -m pytest web/e2e -q`: 4 passed (about 24 s). A first run found two errors in the test, not the page: a locator that matched sidebar rows containing the word "Stopped", and a Python regex with named groups that Playwright cannot hand to JavaScript.
