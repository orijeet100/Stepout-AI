---
date: 2026-10-08
kind: decision
lane: main
status: accepted
title: Secret screening is by patterns, before the model sees file text
tags: [reader, security, redaction]
refs: [docs/plan/v0-finish.md, docs/plan/main-worktree.md, src/stepout/redact.py, tests/test_redact.py]
---

**What.** Text the Reader extracts from a file passes through `redact()` (`src/stepout/redact.py`) before any model sees it. Each match becomes `[redacted]`, and the Finding says how many. The patterns, as decided in [the V0 finish plan](../plan/v0-finish.md):
1. private-key blocks (`-----BEGIN … PRIVATE KEY-----` to its END marker, or to the end of the text if there is none);
2. `sk-ant-…` keys, other `sk-…` keys (20+ characters), AWS access key ids (`AKIA`, `ASIA` and the other prefixes), GitHub tokens (`ghp_…`, `github_pat_…` and kin), Slack tokens (`xox?-…`), JWTs (three base64url parts starting `eyJ`);
3. a **labelled value**: `password`, `passwd`, `pass`, `secret`, `token` or `api key` followed by `:` or `=` and a value. The label stays, the value goes. The label may be a whole part of a longer name, so `db_password=…`, `GITHUB_TOKEN=…`, `AWS_SECRET_ACCESS_KEY=…`, `client-secret: …`, `accessToken: …`, `"api_key": "…"` are caught, while `tokenization`, `Compass`, `Passport` and a bare `Password:` at the end of a line are not touched.

A **model-based** screen is out of V0 (decided in the plan). Screening runs on the text before it is cut to the 40,000 characters sent on, with a little slack, so a secret that straddles the cut is not half-visible.

**Why.** This is the first time the Assistant reads file *contents*. The block list already keeps whole secret files (`.env`, keys, credential folders) from being opened; this is the second layer for secrets inside ordinary files (a notes file with a password in it, a config pasted into a document). Patterns are cheap, fast, deterministic and testable offline; a model screen would cost money on every read, send the secret to the model API in order to find it, and could be talked out of it by the very text it screens.

**What it does not catch** (so nobody relies on it for more). A password described in a sentence; a key split across lines or columns by a PDF's layout; unusual formats; anything that only a human recognises. It is a net. The real boundary is elsewhere and does not depend on it: file contents are untrusted data, and a Run that has read a file cannot reach the web (strict taint, same cycle), so a secret that does slip through cannot be sent out by a URL.

**Two things found while building it** (both tests now). (1) My first labelled-value pattern missed JSON-style `"api_key": "…"` (a closing quote before the colon) and compound names such as `db_password=…`, which is how secrets usually appear; and `\s*` after the colon could swallow a newline and redact the *next* line's first word after a bare `Password:`. (2) A regex that has to look ahead from every start can be made quadratic by a hostile file: with the repeat of name parts unbounded, 42 KB of `a-a-a-…` took **15 seconds**; bounded to four parts it takes 0.01 s. Private-key blocks are therefore found by one linear scan, not a lookahead regex (200,000 BEGIN markers with no END screen in milliseconds).

**Alternatives.** A model screen: see Why. A third-party scanner such as detect-secrets or gitleaks: a new dependency and rule set for a few patterns we can read in one screen. Blocking the whole file when anything matches: loses the useful rest of a resume because of one line.

**Evidence.** `tests/test_redact.py`, 31 tests, offline: every secret shape (invented, assembled from pieces so the repository holds nothing a scanner would flag); the label forms above and the prose that must be left alone; a key plus its label counts once; screening twice changes nothing the second time; the hostile inputs run in hundredths of a second (and the unbounded regex measured at 12 to 15 seconds, so the test would fail on it). Files: `src/stepout/redact.py`, `tests/test_redact.py`.
