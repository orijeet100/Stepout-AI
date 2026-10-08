---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: First run: no key, no grants, no Chrome, a Chrome that died each say what to do
tags: [first-run, chrome, grants, c4]
refs: [src/stepout/app.py, src/stepout/browser.py, src/stepout/files.py, src/stepout/roles.py, tests/test_first_run.py]
---

**What.** Cycle C4, slice 2: a machine that is not set up says so plainly, at start or at first use, and does not crash, hang or blame a safety rule.
- **No `ANTHROPIC_API_KEY`**: `python -m stepout.app` prints "No ANTHROPIC_API_KEY: put it in the .env file next to the app (copy .env.example to .env and fill it in), then restart. Until then every message gets this answer." (`startup_notes`, with the existing grants line) and keeps serving; each message gets the same line as its reply (the `no_key` Failure of the previous slice; no Run is started).
- **No `data/config/grants.toml`**: the start-up line was already there. New: at first use the Files hand now says "outside every grant (no folders are allowed yet: copy grants.example.toml to data/config/grants.toml and list the folders to allow; only the User can do that, so tell them)" when there are no grants at all, instead of the "do not suggest workarounds" refusal it gave for a location the User really had not allowed. The Orchestrator prompt has one exception to "Denied means a fixed safety rule": if the Finding says no folders are allowed yet, that is setup, so tell the user how.
- **No Chrome**: the first `browse` says "Chrome is not installed. Install Google Chrome, then try again." (Playwright's "Chromium distribution 'chrome' is not found"), or "Chrome could not be started (<its first line>)" for any other launch failure, as a `chrome` Failure: the Run fails at once instead of the Browser agent trying eight times, the session is closed, the Ledger has the cause. The check is at first use, not at start: there is no cheap reliable way to ask Playwright whether Chrome is installed without launching it.
- **A Chrome that died** (killed, crashed) between two Runs: `Browser._open_session` now notices (`is_connected()`), drops the dead sessions and starts a new Chrome. Before, every later Run got "could not load the page" until the app was restarted. A real-Chrome test closes Chrome under a Browser and opens a page again.

**Alternatives.** Refusing to start without a key: the page would not load and the reason would be in a terminal the User may not be watching; serving and saying so in the chat is kinder. Pre-checking Chrome at start: see above. A friendlier Files refusal for every disallowed path: an unallowed path is a real boundary and keeps its wording.

**Evidence.** `tests/test_first_run.py` (6; the real-Chrome one skips without Chrome): the start-up notes with and without a key and a grants file; the no-grants refusal (old words kept, setup text added, no "safety rule" or "workaround"); the prompt exception; the two Chrome messages through the real `Browser` with Playwright's real "not found" text, the Run failed after two model calls and the session closed; a Chrome closed under a live Browser is started again. Mutation-checked (each fails a test): the liveness check, recognising a missing Chrome, the no-grants text, the key note. `tests/test_files.py::test_no_grants_means_no_access` still passes unchanged. **Not verified live:** how the real Orchestrator words the no-grants reply (the prompt exception is pinned, its effect is not), and a real machine without Chrome.
