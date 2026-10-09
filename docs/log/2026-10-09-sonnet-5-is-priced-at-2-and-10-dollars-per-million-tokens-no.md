---
date: 2026-10-09
kind: change
lane: main
status: accepted
title: Sonnet 5 is priced at 2 and 10 dollars per million tokens, not 3 and 15
tags: [cost, pricing, model]
refs: [src/stepout/model.py]
---

**What.** `PRICING[SONNET]` in `model.py` is now `(2.00, 10.00)` $ per million tokens (it was `(3.00, 15.00)`). Haiku is unchanged at `(1.00, 5.00)`.

**Why.** Found while pricing the new Pydantic AI adapter: its maintained price table (genai-prices) gives 10,000 input and 1,000 output tokens of `claude-sonnet-5` as $0.03, our table gave $0.045. Reports from August 2026 say Sonnet 5 launched at $2/$10 as an introductory rate, was due to rise to $3/$15 on 1 September, and Anthropic made $2/$10 permanent on 10 August. Our table had the rate that was announced and then cancelled. The error was on the safe side (the $1 cap tripped early and the Ledger over-counted Sonnet by 50%), so no Run was ever under-capped.

**Alternatives.** Fetch prices at run time: rejected, as in ADR 0001 (one more thing that can fail before a Run starts); the Pydantic AI route already uses a maintained table for any model that is re-pointed.

**Evidence.** Two sources agree (genai-prices through `ModelResponse.cost()`, and the August 2026 reports). The reports are secondary; Anthropic's own pricing page was not opened. Costs already recorded for Sonnet Runs (the acceptance figures in STATUS, 8 of 8 for $0.27) were over-counted by up to a third and are not restated. `tests/test_model.py` and the cap tests do not pin the rate and still pass.
