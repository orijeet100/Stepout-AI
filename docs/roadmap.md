# Roadmap

Where the project is and what comes next. The map is [`architecture.md`](architecture.md); how it got here is [`history.md`](history.md).

## State

V0 is built: a read-only task assistant with a web chat, an Orchestrator and four specialists, a live browser view, file reading under Grants, strict taint, a $1 cap per Run (and a monthly limit), saved chats you can search, rename, export and delete, streaming replies, a rebuilt page, **Memory** (a Persona file, History, learned facts; Mem0 or plain files), **one retry policy**, and a Record with tokens, durations, a log and opt-in Capture. Eight acceptance queries pass live for about $0.27; the offline suite passes without a network. It runs on Claude by default and on any provider Pydantic AI speaks when a tier is re-pointed (OpenRouter is the intended route; nothing has run through it yet because no key has been available).

## Next, in order

1. **A live parity run of the Pydantic AI adapter on Claude** (`STEPOUT_STRONG_MODEL=anthropic:claude-sonnet-5`, `STEPOUT_CHEAP_MODEL=anthropic:claude-haiku-4-5`, `scripts/acceptance.py --live`, about $0.30). If it matches the default adapter, delete `AnthropicModel`: one adapter, less code. Streaming has to move to it first (it streams only on the Anthropic adapter today).
2. **Pause, resume and Approvals.** A Question or an Approval pauses a Run and a hint continues the *same* task (today it arrives as a new request). Needs message history and deferred tool calls: the one place the Pydantic AI Agent loop earns its keep ([ADR 0011](adr/0011-pydantic-ai-as-the-plumbing.md)). The first write capability (an upload) asks every time.
3. **Notes** (the Assistant's own know-how about sites, with an expiry: the half of Memory that needs write rules for Untrusted content), the **Evaluation** harness ([0005](adr/0005-two-bounded-contexts.md); Memory off, files and Mem0 are Conditions: `scripts/acceptance.py --memory ... --memory-tasks` and `--compare` are its first form), a **Telegram** channel.
4. **Organize files** (plan, Approval, execute, undo journal; never overwrite or delete).

Done in iteration 2 and no longer on this list: Memory, the retry policy, chat management, the log, a monthly limit ([history](history.md)). A live comparison of the three Memory conditions is the next measurement.

## Parked ideas

Smarter file search (ask with options, rank folders, skip `node_modules`, `.git` and venvs, fuzzy names) · a Verifier that checks the answer against its sources before replying · a separate Planner and parallel steps · streaming for specialists' Findings · relaxing strict taint to "sites the User named" · a model picker and message actions in the page.

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

## Open questions

Is a click Consequential (once pointer actions exist)? Evaluation matrix size against the monthly budget.
