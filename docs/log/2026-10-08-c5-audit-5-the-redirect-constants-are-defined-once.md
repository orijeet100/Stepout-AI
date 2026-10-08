---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: C5 audit 5: the redirect constants are defined once
tags: [cleanup,audit,fetch,browser]
refs: []
---

**What.** `MAX_HOPS` and `REDIRECTS` live in `fetch.py` and `browser.py` imports them (it already imported the network policy from there).

**Why.** Both files had the same two constants (5 hops, status codes 301/302/303/307/308). The Fetcher and the Browser must agree on what a redirect is and how far to follow one; two copies is the way they stop agreeing.

**Alternatives.** Moving them to a new module: three lines do not need one.

**Evidence.** Offline suite green (`tests/test_fetch.py`, `tests/test_browser.py` against real Chrome included). Files: `src/stepout/fetch.py`, `src/stepout/browser.py`.
