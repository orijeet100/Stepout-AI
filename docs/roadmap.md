# Roadmap

Where the project is and what comes next. The map is [`architecture.md`](architecture.md); how it got here is [`history.md`](history.md).

## State

V0 is built: a read-only task assistant with a web chat, an Orchestrator and four specialists, a live browser view, file reading under Grants, strict taint, a $1 cap per Run (and a monthly limit), saved chats you can search, rename, export and delete, streaming replies, a ChatGPT-style page (light and dark, agent work drawn as a plan, task cards and tool calls), **Memory** (a Persona file, History, learned facts; Mem0 or plain files; each entry editable in the page), **one retry policy**, and a Record with tokens, durations, a log and opt-in Capture. Eight acceptance queries pass live for about $0.27; the offline suite passes without a network. It runs on Claude by default and on any provider Pydantic AI speaks when a tier is re-pointed (OpenRouter is the intended route; nothing has run through it yet because no key has been available). It installs in one command (`stepout`) into its own Home folder, and a phone can reach it through Tailscale Serve (`stepout remote`); both are built. The phone link has run for real once, on one Windows laptop with a real tailnet (2026-10-12); starts now repair it and check it before they announce it ([ADR 0019](adr/0019-one-command-install.md), [ADR 0020](adr/0020-phone-access-through-tailscale-serve.md), [ADR 0021](adr/0021-start-repairs-itself.md)).

## Next, in order

1. **A live parity run of the Pydantic AI adapter on Claude** (`STEPOUT_STRONG_MODEL=anthropic:claude-sonnet-5`, `STEPOUT_CHEAP_MODEL=anthropic:claude-haiku-4-5`, `scripts/acceptance.py --live`, about $0.30). If it matches the default adapter, delete `AnthropicModel`: one adapter, less code. Streaming has to move to it first (it streams only on the Anthropic adapter today).
2. **Pause, resume and Approvals.** A Question or an Approval pauses a Run and a hint continues the *same* task (today it arrives as a new request). Needs message history and deferred tool calls: the one place the Pydantic AI Agent loop earns its keep ([ADR 0011](adr/0011-pydantic-ai-as-the-plumbing.md)). The first write capability (an upload) asks every time.
3. **Notes** (the Assistant's own know-how about sites, with an expiry: the half of Memory that needs write rules for Untrusted content), the **Evaluation** harness ([0005](adr/0005-two-bounded-contexts.md); Memory off, files and Mem0 are Conditions: `scripts/acceptance.py --memory ... --memory-tasks` and `--compare` are its first form), a **Telegram** channel.
4. **Organize files** (plan, Approval, execute, undo journal; never overwrite or delete).
5. **The rest of the first real runs.** The phone link ran for real on one Windows laptop and an iPhone (2026-10-12), and `v0.1.0` went through the release workflow (published 2026-10-15; its URL installs into an empty folder). Still to do: a fresh machine that never had Tailscale, which is also the first live run of the winget install (its id was wrong until 2026-10-16); and macOS, as a separate plan ([the plan](plans/2026-10-16-001-feat-macos-support-plan.md), [ADR 0021](adr/0021-start-repairs-itself.md)).

Done in iteration 2 and no longer on this list: Memory, the retry policy, chat management, the log, a monthly limit, the one-command install and Home, phone access through Tailscale Serve, which now repairs itself at each start (built; its first real run is done, and item 5 has the rest) ([history](history.md)). A live comparison of the three Memory conditions is the next measurement.

## Parked ideas

Smarter file search (ask with options, rank folders, skip `node_modules`, `.git` and venvs, fuzzy names) · a Verifier that checks the answer against its sources before replying · a separate Planner and parallel steps · streaming for specialists' Findings · relaxing strict taint to "sites the User named" · a model picker in the page · the optional Folders panel and Explorer menu (plan U10, left out) · `stepout init --provider` (other providers' keys in one step; for now a line in Home's `.env`) · a PyPI release (`uvx stepout`; a public name claim, so not yet) · `stepout remote --always-on` (start the chat at login so the phone link survives a reboot: a Task Scheduler entry on Windows, a LaunchAgent on a Mac; opt-in and removable) · Linux and Windows on ARM (not supported or tested; Files fails closed off Windows).

## Known code debt (from the 2026-10-11 audit)

| Debt | Why it matters | Fix |
|---|---|---|
| Two model adapters (Anthropic SDK and Pydantic AI) | double the maintenance, and only one streams | item 1 above |
| `Runner._hands` wires hands by name | contradicts "a tool is one file plus one line" | inject a name-to-hand mapping |
| "No file contents entered" is set as a side effect inside `read_text` | a future tool that returns file text must remember to set it | declare it on the capability next to `reaches_web` |
| A Finding is free text; the Runner finds URLs in it by regex | a lossy hand-off | a typed Finding, only if evaluation shows it matters |
| The Orchestrator prompt lists the Roles by hand | duplicates the `ROLES` table | generate that part of the prompt |
| Costs recorded before 2026-10-09 priced Sonnet at $3/$15 | over-counted by up to a third | none; documented |
| Mem0's own embedding client keeps its own retries; its cost is an estimate | the one gap in "one retry policy" and in the Ledger's cost | route embeddings through our Model port if it matters |
| Recollection relevance and its size budget are untuned | Memory may hand over too little or too much | the live comparison, then tune |
| Browser navigation has no retry, and the Fetcher's is the only tool retry | a transient page failure costs a step | when the Evaluation shows it |

## Known design debt (from the 2026-10-16 audit; the rules are in [`design.md`](design.md))

| Debt | Why it matters | Fix |
|---|---|---|
| `index.html` is served with no `Cache-Control`, and a build deletes the old hashed assets | a browser holding the old `index.html` asks for files that are gone until it is hard-reloaded (seen when rebuilding under a running page) | `Cache-Control: no-cache` on the index response (`_index` in `channels/web.py`) |
| The 375px header and the missing-screenshot placeholder are CSS fixes with no automated test | a stylesheet edit can bring either back without a red test | a Playwright flow at 375px beside `web/e2e/test_drawer.py`, and a computed-style check of the placeholder in dark |
| Chats saved before 2026-10-15 keep titles cut mid-word | the list shows "…a table and so" | a one-off repair: where a title equals its first message cut to 60, set `chat_title` of that message |
| No accent colour; the logo's colours appear nowhere in the page | it looks like any chat app | a decision, see `design.md` Open |
| Suggestions are a ragged stack of pills | they read as leftover | a 2 by 2 grid of equal pills |
| Row tools stay 28px on touch | a small target in the drawer | 44px under `pointer: coarse` if the row still fits a title |
| The phone drawer has no close button | only the scrim, Esc or choosing a chat closes it | a close button in the drawer's head under 900px |
| The header title and the conversation column do not share a left edge | looks unaligned on a wide screen | a taste call: align the title to the column, or leave it as ChatGPT does |

## Open questions

Is a click Consequential (once pointer actions exist)? Evaluation matrix size against the monthly budget.
