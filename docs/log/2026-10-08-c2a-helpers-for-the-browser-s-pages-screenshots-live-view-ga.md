---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: "C2a: helpers for the browser's pages: screenshots, live-view gate, safe addresses"
tags: [c2,live,security]
refs: [web/src/runview.ts, web/src/runview.test.ts]
---

**What.** Pure helpers the live view and the screenshot viewer build on. `shotsOf(run)`: a Run's `shot` events as `{path, url, title}`, in order. `hasBrowserStep(run)`: the Browser agent has acted (a `step` by the `browser` Role), which is the only time there is a page to watch. `shotSrc(path)`: the address of a saved screenshot, but **only** for the `<32 hex>/<n>.jpg` the backend writes, otherwise `null`, so the page never builds an image address from anything else. `safeHref(url)`: a page's address as a link target **only** if it is `http` or `https`; everything else (`javascript:`, `data:`, `file:`, `//host`, relative, empty) is `null` and shows as plain text.

**Why.** The URL and title of a shot come from a web page the model opened, so they are untrusted text (the security rule for model output in `docs/ui-contract.md`); the `shot` path is built by the backend, but the page still checks its shape before using it as an image address.

**Alternatives.** Trusting the backend's `shot` path as is (one bug or a hostile event would turn it into an arbitrary image request). Linking whatever URL arrives (a `javascript:` link from page-supplied text).

**Evidence.** `npm test`: 65 passed, including 10 rejected spellings of a screenshot path (traversal, wrong extension, query string, upper case, an absolute URL, `//host`, an encoded slash) and 9 rejected link schemes. Build and lint clean.
