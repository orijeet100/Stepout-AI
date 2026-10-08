---
date: 2026-10-07
kind: decision
lane: main
status: accepted
title: Front door v0 is one Haiku call; Jev is deferred
tags: [intake, screening, jev, cost]
refs: [docs/plan/main-worktree.md]
---

**What.** Intake becomes **one Haiku call** with a structured answer: decline (with reason), a short chat reply (greetings, thanks, "what can you do?" only), or proceed, plus the numbers of related earlier Exchanges. The "can we do this?" list is assembled from the capability modules. The regex decline list, the unused `Route` and its classifier call are **deleted**. If the call fails, the message proceeds (with the last 3 Exchanges attached). The front door sits behind a **Screening port**, so Jev can drop in as an adapter if a measurement says it is faster or cheaper. Hard authority stays where it already is: the read-only rule, the Gate and, later, Approvals.

**Why.** Haiku answers every question Jev would in this pass for about $0.001 a message (Haiku is $1/$5 per million tokens in `model.py`; about 800 tokens in), with no new vendor, no early-access key, and no user text sent to a third party. The Runner never read `Route`. The regex is worse than useless: it misses paraphrases **and** wrongly declines legitimate requests.

**Alternatives.** Jev for screening and follow-up detection: deferred, not rejected. Always attaching the last 5 Exchanges: new tasks would carry history, it is resent at every Orchestrator step, and hostile text in an old reply could reach unrelated tasks. Keeping the regex as a first layer: rejected, see the evidence.

**Evidence.** Probe of `gate.screen` on 2026-10-07. Misses: 7 of 10 should-decline paraphrases were accepted (`send $200 to my landlord`, `wire money to John`, `write me a python script`, `close my bank account`, ...). False declines: 7 of 7 legitimate requests containing a trigger word were declined (`how do I pay attention in long meetings`, `what is the cancellation policy for Airbnb`, `delete the duplicate lines from this list`, `find a sign up sheet template`, `summarize this article about password managers`, `what is a transfer window in football`, `explain how invoice factoring works`). A 50-prompt labeled set, including these, is part of iteration B3.
