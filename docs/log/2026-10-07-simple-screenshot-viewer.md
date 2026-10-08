---
date: 2026-10-07
kind: decision
lane: ui
status: superseded
title: Screenshot viewer is a simple big view, no cursor replay or streaming
tags: [ui, viewer, browser]
refs: [docs/plan/ui-worktree.md]
---

**What.** Page screenshots show as thumbnails in the run view. Clicking one opens a large viewer: the page's URL and title, previous/next across the run, Esc to close. No cursor animation, no live screencast, no take-over view.

**Why.** The agent never clicks pixels: it opens a URL or follows a numbered link. A simple, honest view is enough. The User asked for it simple.

**Alternatives.** An animated cursor replay; a CDP screencast; a take-over view (conflicts with the read-only, isolated browser, ADR 0010).

**Evidence.** Browser capabilities are `open`, `click` (a numbered link) and `more` in `browser.py`.
