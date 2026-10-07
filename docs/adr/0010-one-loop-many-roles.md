# 0010 — One loop, four Roles

Status: accepted · 2026-10-07 · replaces the roadmap's "sub-agents later". [ADR 0001](0001-from-scratch.md) still holds: no agent framework.

**Decision.** The Runner's agent loop runs under a **Role**: a system prompt, a tool set, a model and a Step cap. V0 has four. The **Orchestrator** receives the Task and has no hands — it can only Delegate, ask the User, or answer. **Direct** has fetch and search. **Browser** has the Browser module. **Files** has `find` / `list` / `stat` / `read` in read Mode only — it never organizes or writes (organizing stays S11). A specialist runs the same loop with its own tools and hands back a **Finding**. One loop function plus a Role table; each slice adds the Role for the hand it builds (S1b Orchestrator + Direct, S2 Browser, S8 Files). Driving the desktop by screenshot and clicks ("computer use") is out of V0.

**Rules.** (1) Every Action from every Role passes the one Gate. (2) Budget, Taint, the Approval list and the Ledger are per Run: a specialist that reads file contents Taints the whole Run, and the $/Task cap covers every call. (3) A Finding is Untrusted content — never an instruction, never Memory, never a permission. (4) Only the Runner talks to the User; a specialist's Question or Approval is raised by the Runner. (5) Delegation is one level deep. (6) Every Ledger event records its Role and its parent; Checkpoints save the active Role stack. (7) Evaluation adds a second Condition, one loop versus orchestrated, with the single loop as the Control.

**Why.** Specialists keep heavy context (page views, file text) out of the Orchestrator's. Each Role can use the cheapest model that holds up. A Role with one hand is a smaller target: a poisoned page that steers the Browser Role cannot read a file, and the Direct Role cannot click.

**Rejected.** A multi-agent framework (hides the part we measure, ADR 0001). Computer use (the Gate cannot classify a click at pixel coordinates, so every click would either Ask or pass; the Browser Role already covers the web). Free-form agent-to-agent chat (no shared state to bound or audit). All Roles at once (each lands with its hand).

**Cost to watch.** Orchestration adds model calls to a $0.50/Task cap. The S6 Condition measures it; if orchestration does not pay for itself on the Golden tasks, the single loop stays as the default.
