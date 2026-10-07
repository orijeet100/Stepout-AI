# 0005 — Two bounded contexts: Assistant and Evaluation

Status: accepted · 2026-10-06

The product and the proof speak different languages — Task, Question, Approval versus Trial, Condition, Intervention — and the proof must never shape the product. So Evaluation drives the Assistant only as a Channel (the Simulated user) and reads its Ledger; the Assistant never decides what counts as an Intervention. Considered: evaluation helpers calling the Runner directly (faster, but the Assistant would be graded by code reaching past its interface, which weakens the claim). Also rejected: splitting the Assistant into more contexts (conversation, tasking, memory, authority) — one language holds across them, so they are modules, not contexts.
