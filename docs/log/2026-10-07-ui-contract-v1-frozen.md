---
date: 2026-10-07
kind: contract
lane: both
status: accepted
title: UI contract v1 frozen at sync X1
tags: [contract, ui, x1]
refs: [docs/ui-contract.md]
---

**What.** The User signed off `docs/ui-contract.md` v1 as proposed. Settled points: a chat's title is the first request cut to 60 characters; `queued` in the chat list and in `status` is enough; the cost footer leaves the reply text at sync X2, once the page reads `cost_usd`. Also accepted: `cap_usd` on the status frame and on runs (so the progress meter can compare spend with the Run's budget), and `url` and `title` on `shot` events (so the screenshot viewer can caption a page).

**Why.** Both lanes build against one agreed wire format, so they can work in parallel; B2 (Main) and U2 (UI) are unblocked.

**Alternatives.** A model-written chat title (costs a call per chat); a separate status route instead of a frame.

**Evidence.** The "Settled at sign-off" section of the contract.
