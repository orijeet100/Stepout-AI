---
date: 2026-10-11
kind: decision
lane: main
status: accepted
title: "Slice 4 (the loop on Pydantic AI Agents) is not built: about 20 lines of plumbing against our own logic"
tags: [pydantic-ai, runner, adr]
refs: [docs/adr/0011-pydantic-ai-as-the-plumbing.md, src/stepout/runner.py]
---

**What.** [ADR 0011](../adr/0011-pydantic-ai-as-the-plumbing.md) planned slice 4 as the loop itself: one Pydantic AI `Agent` per Role, the Gate as a hook, `cancel()` for Stop, `UsageLimits` for the cap, a typed `Finding`. It is **not built**. The Runner stays as it is; Pydantic AI stays under the model (slice 1), the search (slice 2) and the tool definitions (slice 3 needed no library at all).

**Why.** The three unknowns the ADR listed were probed offline first, and all three came back workable: a specialist's step cap can sit next to a shared budget (write its limit as the parent's requests so far plus N); the default full history sends about the same as our notes (30,150 against 30,100 characters in a five-request run, a long page view needs a history processor as `compact` does today); the library has hooks around model requests, tool calls, runs and nodes. So the slice is feasible. It is not worth it: `runner.py` is 279 lines, and what a library replaces is `_unless_stopped` (14 lines), the cap check (about 3) and `_stop` (4), roughly 20 lines. The other 80-odd lines of `_agent` are the Gate call, the repeat guard, plan and delegate, the compaction, the taint and the Trace: the logic ADR 0001 says we build and defend. Replacing them means re-expressing each as a hook, bridging 20 test files that script our `Model` port (`Harness`, `ScriptedModel`), and re-running the live acceptance set, for no new capability. A typed `Finding` is not a library feature either: it would make every specialist emit more fields (more tokens and more ways to fail) to replace a regex that works.

**Alternatives.** Build it anyway: it is reversible and the evidence says it works; it would be chosen for reasons outside the code (one framework's vocabulary throughout, its observability, a later move to its durable execution), and then it is a real choice for the User to make. A thinner version, one specialist Role on an `Agent` behind the existing seam: two loops to keep in step, so no.

**Revisit when.** (1) Pause/resume and Approvals (B5) begin: they need a message history and deferred tool calls, which is the one thing the library gives that the Runner lacks; adopt it for that path then. (2) A provider's tool-calling cannot be driven by our stateless notes. (3) The User asks for it for the reasons above.

**Evidence.** The probe (`pydantic-ai 2.54.0`, `FunctionModel`, no network): shared usage with a naive limit stopped the child at 2 requests of 3 needed; with `parent requests + 3` it made 3 and finished; unshared, the parent's total did not include the child. `runner.py` function sizes by `ast`: `_agent` 83, `submit` 23, `__init__` 21, `_unless_stopped` 14, `_run_step` 12, `_previous_block` 11, `_summary` 11, `_state` 9, `_failed` 6, `_emit` 6, `_stop` 4. The offline suite is unchanged at 544.

**Not checked.** What the rewrite would cost in tokens on the live set (it was not built). The estimate of the test bridge is a judgement from 20 files using the harness, not a measurement.
