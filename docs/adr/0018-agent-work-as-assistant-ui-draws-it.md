# 0018 — A Run is drawn as assistant-ui draws agent work: a plan, task cards, tool calls

Status: accepted · 2026-10-12 · amends [0017](0017-the-page-follows-the-chatgpt-look.md) (the run card)

**Decision.** The run card follows four assistant-ui designs (assistant-ui.com: Agent Tool, Agent plan, Subagent list, Task card), rebuilt in our CSS from their markup and measured sizes (13.5 px text, 11 px mono tags, 3 px bars, 16 px cards with a 14 by 10 px inset):

- **The Run** is one quiet line (chevron, the summary, a state icon) that opens; it is open while the Run works and closed once it ends. Its count is the tool calls you can see ("1 action"), not every model call behind them (planning, delegating and answering are not actions).
- **The plan** (two steps or more; one step is just its task card) is the Agent plan: a title and "n of m", a thin bar, a checklist with a tick, a spinner or a dot; only the step in progress names its agent. The budget uses the same header and bar.
- **A delegation is a task card.** Each plan step handed to a specialist is the Task card (state, goal, agent, time, a chevron, its result under a rule) with the Subagent list's model tag and bar. It is open while it works.
- **A hand action is a tool call.** Inside a task, each action is the Agent Tool line: what it did in plain words ("Searched the web", "Opened a page"; "Searching the web" while it runs), the argument in a chip, and a tick, spinner or cross. It opens onto the request (and what the model call cost) and the result. Retries and a Memory miss are lines of the same kind, without a chip; Memory doing its job is not a line (the Memory panel shows what it keeps).

**The layer.** `workOf(run)` in `runview.ts` turns a Run's events into tasks and tool calls; the components (`AgentPlan`, `TaskCard`, `ToolCall`) only draw what it gives them. A delegation is the events whose `parent` is the Orchestrator's plan or delegate step, and its goal is the step the next `plan` event marks running. The page now reads `action` (its plain fields), `model` and `repeat` from a `step`, which the contract already carries. The backend is unchanged.

**Honest numbers kept.** A tool call has no percentage, so a task's bar sweeps while it works and fills once it ends, never a made-up value. A `return` after a stop does not relabel the task "failed", and a Run that ends before its task reports back leaves that task stopped, not spinning.

**Not taken from assistant-ui.** Its runtime, toolkit and Tailwind (no new dependency); the "Show N more" lane limit (a Run has at most a handful of tasks); the approval controls (there are no approvals yet).

**Why.** The User asked for agent and tool calls to look like these designs. They also read better than the old step table: whose work it was, what each action did and how it ended can be seen at a glance, and the detail is one click away.

**How it was checked.** Six unit tests for `workOf` against the fixtures (tasks, calls, a refusal, a stop, a Run cut short), the run-view component tests rewritten for the new parts, the real-Chrome flows (a task and its call opened, the live run filling in, reduced motion), and the page compared with the four reference pages in a browser, side by side, in dark and light.
