# 0010 — One loop, five Roles

Status: accepted · 2026-10-07 · amended 2026-10-07 (Plan, Reader, read-only V0-basic) · replaces the roadmap's "sub-agents later". [ADR 0001](0001-from-scratch.md) still holds: no agent framework.

**Decision.** The Runner's agent loop runs under a **Role**: a system prompt, a tool set, a model and a Step cap. V0 has five, each holding exactly one kind of hand:
- **Orchestrator** — in charge of the Run, no hands. It writes a **Plan** (a short list of steps: Role, goal, status), Delegates one step at a time, re-plans if a step fails (at most twice), asks the User, and reports. Only it talks to the User.
- **Direct** — fetch and search.
- **Files** — finds files: `find` / `list` / `stat` / `count`. Names, counts, sizes and dates only; it never sees contents.
- **Browser** — a headless browser (fresh, isolated, no logins), read-only: navigate, read the page, scroll, follow links.
- **Reader** — `read_text(path)` for paths the Orchestrator names: text and PDF extraction, secret screening, truncation. It returns a **Finding**, so the Orchestrator never holds raw file text.

A specialist runs the same loop with its own tools and hands back a Finding. One loop function plus a Role table; no separate Planner agent. Driving the desktop by screenshot and clicks ("computer use") is out of V0.

**Rules.** (1) Every Action from every Role passes the one Gate. (2) Budget, Taint, the Approval list and the Ledger are per Run: one **$1 Budget** covers every Role's calls (at most 3 web searches), and reading file contents Taints the whole Run. (3) A Finding is Untrusted content — never an instruction, never Memory, never a permission. (4) Only the Runner talks to the User; a specialist's Question is raised by the Runner. (5) Delegation is one level deep, one step at a time. (6) Every Ledger event records its Role and its parent, and every call, return, Action and Verdict streams live to the page as the **Trace**; Checkpoints save the active Role stack. (7) V0-basic is **read-only**: anything that types, submits, uploads, downloads, moves or deletes is Refused until Approvals exist (S3). (8) Once a Run has read file contents, web search, fetch and browsing are limited to sites the User named in the request. (9) Evaluation adds a second Condition, one loop versus orchestrated, with the single loop as the Control.

**Why.** Specialists keep heavy context (page views, file text) out of the Orchestrator's. Each Role can use the cheapest model that holds up. A Role with one hand is a smaller target: a poisoned page that steers the Browser cannot read a file, and the Direct Role cannot click. The Orchestrator plans because the agent that sees the Findings is the one that must re-plan; a separate Planner adds a model call and a hand-off that loses information, and the User wants one agent in charge of the log. Reading is its own Role so contents reaching the model happen in one visible, budgeted, Taint-setting step.

**Later, if evidence says so.** A Verifier that checks the answer against the goal and sources before replying (V0.5). A separate Planner, parallel steps and plan approval for risky Tasks (V1) — promote `make_plan` to a Role if Evaluation shows plan quality, not execution, is the bottleneck.

**Rejected.** A multi-agent framework (hides the part we measure, ADR 0001). Computer use (the Gate cannot classify a click at pixel coordinates, so every click would either Ask or pass; the Browser Role already covers the web). Free-form agent-to-agent chat (no shared state to bound or audit). All Roles at once (each lands with its hand). Attaching to the User's everyday Chrome (their logged-in tabs would be reachable by whatever a hostile page talks the model into).

**Cost to watch.** Orchestration adds model calls. The Run cap is $1; the S6 Condition measures whether orchestration pays for itself, and the single loop stays as the Control.
