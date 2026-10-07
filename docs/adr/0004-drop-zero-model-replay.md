# 0004 — Drop "replay with zero model calls"; measure interventions

Date: 2026-10-06 · Status: accepted · Supersedes the brief's headline number

**Decision.** Zero-model replay is not a requirement and not the headline metric. A model decides every step. The headline is **human interventions per task across repeated attempts**, against a memory-off control, at equal or better success. A deterministic fast path may be revisited later, only if measurements show it's worth it.

**Why.** The owner's goal is a remote assistant that finishes jobs from a phone, asks for help when stuck, and gets better with experience — not a cost trick. The old design (per-step expectations as a replay gate, a "zero model calls" test) existed only to make replay safe.

**Consequences.** Saved know-how becomes guidance the model reads at the start of a run, not a script. The workflow/replay/heal vocabulary is retired. Improvement is memory-driven; no model is trained, and the write-up says so.
