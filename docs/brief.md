# Original brief (verbatim, 2026-10-06)

> Source of intent. Do not edit; supersede it with `docs/requirements.md` and `docs/adr/` instead.

Project Brief: Record-Once, Replay-Cheap Browser/Computer Agent
Hand this to Claude as context, then say: "Let's brainstorm and refine this, then start building."
1. One-line pitch
An agent you control from your phone that drives a browser (and optionally your computer). You show it a task once, it saves the task as a parameterized workflow, and later runs replay the saved steps with no model calls, falling back to the model only when a page changes, then patching the workflow so it heals itself.
The number to prove: "The same task cost $X on the first run and $0.0Y on replays, at the same success rate."
2. About me and my goals

* Applied AI / forward-deployed engineer. Comfortable with Python, TypeScript, Pydantic AI, Langfuse, MCP, function calling, Postgres, Docker basics.
* Main goal: learn how production AI agents really work (sandboxing, permissions, state, retries, tracing, evals) by building something genuinely cool.
* Secondary goal: a project I can show in interviews, with real numbers and a write-up.
* Scale: me plus a few trusted users, not thousands.
* Budget: minimal. I want to avoid spending hundreds of dollars. Model spend is the main cost, so cost control is a feature.
* I prefer proven abstractions over writing everything from scratch (browser-agent libraries, existing MCP servers, managed tracing), and I'll hand-build only the parts that define the project.

3. Scope
In (v1):

* Record a task (demonstration or natural-language description) into a saved workflow.
* Replay workflows deterministically with parameters, no LLM calls on the happy path.
* Self-healing: when a step fails, hand control to the model, finish the task, and propose a patch to the workflow.
* Browser execution in a container (Docker + Playwright/Chromium), with a live view so I can watch or take over.
* Control from my phone through one chat channel (Telegram first) behind an adapter.
* Per-task permission contracts (allowed domains, allowed actions, hard stops) enforced outside the model, plus approval gates before irreversible actions.
* Tracing (Langfuse) and cost/step/time caps per run.
* A minimal local file helper later in the project, so tasks can pull from or save to allowed folders on my computer.

Out (for now):

* A reliability scoreboard or dashboard (deliberately deferred). Keep basic per-run logs only.
* Multi-tenant accounts, billing, or any real user-management system.
* Driving my real desktop apps (full computer use). Design for it via the Driver interface, but don't build it yet.
* Defeating CAPTCHAs, 2FA, or bot detection. These are handed off to me.
* Booking, paying, or sending without explicit approval.

4. Architecture sketch

```
Phone / Telegram (adapter, allowlisted senders)
        |
   Gateway + task queue (SQLite or Postgres)
        |
   Orchestrator
     - run modes: RECORD, REPLAY, HEAL
     - budgets (steps, time, tokens, cost)
     - permission contract enforcement
     - approval gates
     - tracing
        |
   Driver interface (screenshot, navigate, click, type, read page, upload, download)
     |- ContainerBrowserDriver: Docker + Playwright + noVNC live view
     |- LocalFileDriver (later): hub <-> helper on my computer, outbound connection, allowed folders only
        |
   Results back to chat: extracted data, files, screenshots

```

Key design choice: everything the agent can do goes through the Driver interface, so the container and my own machine are interchangeable implementations.
5. The core idea: workflows
A workflow is a saved, parameterized list of steps. Each step should carry enough information to find its target again without a model:

* action type (navigate, click, type, select, upload, wait, extract, assert)
* target description (human-readable) plus several locator strategies (role + accessible name, text, CSS, XPath, position as a last resort)
* parameters it consumes (for example `{search_term}`)
* expected outcome (an assertion: URL pattern, element present, text visible)
* risk tag (read-only, reversible, irreversible), which drives approval gates

Record modes to explore:

1. Describe it: I give a natural-language task, the agent does it with the model once, and the successful action trace is distilled into a workflow.
2. Show it: I perform the task in the live view, and the actions are captured.
3. Hybrid: the agent drafts, I correct, and the corrections are saved.

Replay: execute steps in order, check each step's assertion, and substitute parameters. No model calls unless a step fails.
Self-healing: on a failed step, pass the model the workflow's intent, the failed step, a screenshot, and the page state. The model completes the step (or the remaining task). If it succeeds, propose a patched step (new locator or an added step) and either apply it automatically for low-risk steps or ask me to approve it. Never silently change irreversible steps.
Open design questions:

* How should targets be represented so they survive minor page changes (accessibility tree vs DOM vs visual)?
* When is a step "failed" versus "slow" (wait and retry policy)?
* How do we detect that the page is different enough that the workflow is no longer valid?
* How do we version workflows and roll back a bad patch?

6. Permission contract (safety layer)
Each workflow declares up front:

* allowed domains
* allowed action types and the risk tag of each step
* files it may read or write (paths or folders)
* data it may extract and where it may send it
* budget caps (steps, time, cost)
* steps that always require approval

Rules:

* Enforcement lives in the orchestrator, outside the model. The model cannot widen its own permissions.
* Page content is untrusted data, never instructions.
* Credentials are injected at the browser layer and never placed in model context.
* Approval messages show the exact action (for example the real recipient and text), with one-tap approve or deny.
* Every run produces an audit log: pages visited, actions taken, actions blocked.

7. Suggested stack (verify current versions and terms before committing)

* Language: Python (orchestrator) with Pydantic models for workflow schemas.
* Browser: Playwright + Chromium in Docker; noVNC or screenshot streaming for live view.
* Agent layer for record and heal: a browser-agent library (browser-use, Stagehand, or Playwright MCP) or the model API's computer-use tool. Decide after reading their code.
* State: SQLite to start, Postgres if needed.
* Chat: Telegram bot behind a channel adapter.
* Observability: Langfuse (cloud free tier or self-hosted) plus structured logs.
* Remote access to the live view: Tailscale or Cloudflare Tunnel.
* Evals and tests: Pydantic Evals or plain pytest, run in CI.

8. Cost plan

* Phase 1: everything on my laptop (free).
* Phase 2 (optional): hub and containers on a spare machine at home or a small cheap VPS. Only the file helper runs on my main computer.
* Model cost control: hard monthly cap in the provider dashboard, per-run cost logging, cheap models for routine steps and a stronger model only for recording and healing.
* Replay costs close to zero by design, which is the whole point.

9. How we'll measure success (kept minimal)

* Workflow cost: first run versus replay run, for 3-5 real tasks.
* Replay success rate over repeated runs (for example 20 runs per workflow).
* Self-heal test: deliberately change a test page (rename a button, move an element) and check whether the workflow heals, escalates, or fails.
* Safety test: a handful of poisoned pages (hidden "ignore your instructions" text, fake approval prompts), with zero unauthorized actions as the target.

Test against sandbox pages I control, plus sites whose terms allow automation, not arbitrary real sites.
10. Week-one plan

1. Docker image with Chromium, Playwright, and a live view.
2. Driver interface with the container browser implementation.
3. Workflow schema (Pydantic) and a hand-written workflow that replays on a test page.
4. RECORD mode: describe a task, the agent does it, and the trace is distilled into a workflow.
5. REPLAY mode with assertions and parameters.
6. Telegram adapter: start a task, get status and screenshots, approve or deny.
7. Langfuse traces and per-run step/time/cost caps.
8. Baseline: record one task, replay it 10 times, and record cost and success rate.

Week two: HEAL mode and patching, the permission contract enforcer, poisoned-page tests, then the local file helper and an offline task queue.
11. Constraints and cautions

* Many sites prohibit automation in their terms. Use sandbox sites and sites that allow it.
* CAPTCHAs, 2FA, and bot checks are handed off to me, not bypassed.
* Irreversible actions (pay, send, delete, submit) always stop for approval.
* Don't share a browser profile that is logged into my personal accounts with other users.

12. How I want Claude to work with me on this

* Start by challenging the design: what's weak, what's already solved by an existing tool, what could be cut.
* Before suggesting a library, check that it's current and maintained.
* Keep scope tight. Push back if I add features before the week-one baseline works.
* Prefer small end-to-end slices over finished components.
* Explain tradeoffs briefly, then recommend one option.

13. First brainstorm questions

1. What are the 3-5 concrete tasks I'd record first, so the workflow design is driven by real use?
2. Accessibility tree, DOM, or visual targeting: which locator strategy should be primary?
3. Which existing browser-agent library should I build on, and what should I read first?
4. What is the simplest honest definition of "self-healed", and how do we avoid bad patches?
5. What does the Telegram approval message look like for a workflow step?
6. What is the smallest demo that makes the cost-per-run number obvious?
