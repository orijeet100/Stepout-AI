# History: what was decided and what was built

The choices that shaped the product, in the order they happened, with where to read more. The small changes are in `git log`.

## 2026-10-06: the starting choices

| Choice | Why | |
|---|---|---|
| **Build what we measure, borrow plumbing** (Playwright, the Anthropic SDK, Pydantic, aiohttp); no agent framework | the goal is to learn how production agents work | [ADR 0001](adr/0001-from-scratch.md) |
| **One process on the laptop**; no Docker, cloud, email or credentials in V0 | scope; files and the browser are the point | [0002](adr/0002-laptop-only-v0.md) |
| Memory is **plain files first**, mem0 later as a measured challenger | measurable, and replaceable | [0003](adr/0003-memory-files-first.md) |
| **Interventions per task** is the headline metric ("replay with zero model calls" dropped) | an honest claim | [0004](adr/0004-drop-zero-model-replay.md) |
| **Two contexts**: Assistant and Evaluation; the Assistant never grades itself | trust | [0005](adr/0005-two-bounded-contexts.md) |
| **SQLite** behind one `Store` | simple now, Postgres later | [0006](adr/0006-sqlite-for-runs-and-ledger.md) |

## 2026-10-07: the design settles, and the first working build

- **Actions and Results are plain data** so the hands can move off the laptop in V1 ([0007](adr/0007-brain-and-hands.md)).
- **Laptop files only through Grants**, a fixed block list, and Taint ([0008](adr/0008-laptop-files-grants.md)).
- **The page is React** served by the Python process ([0009](adr/0009-react-web-page.md)).
- **One loop, five Roles**: an Orchestrator that plans as data and specialists that each hold one tool, so a hijacked page can only misuse what that one tool can do ([0010](adr/0010-one-loop-many-roles.md)).
- **Built:** the domain core and a terminal; the web chat; the Orchestrator (a news question went from $0.26 on a single loop to $0.07); the Files agent (a real D: drive counted, `.env` refused); the headless Browser agent with every request and redirect checked.
- **Tools became one file each** (the capability registry), so adding a tool never touches the Runner, Gate or model adapter.
- **The front door** ([ADR 0012](adr/0012-the-front-door.md)): one cheap model call per message replaced a regex decline list that missed 7 of 10 paraphrases and wrongly declined 7 of 7 harmless requests.
- **Chats are saved** and a follow-up is linked to the exchange it depends on, not just the last one.
- **One run at a time** across all chats (a single Stop flag, simpler spend); events already carry run and chat ids, so parallel runs need no contract change.

## 2026-10-08: the Reader, safety hardening, and a V0 you can use

- **The Reader** reads the text of files and PDFs. **Strict taint**: after any read the run has no web at all, and a follow-up that builds on it starts the same way (relaxing this to "sites the User named" was left out as YAGNI). Secret-looking values are redacted by patterns before any model sees the text; patterns, not a model, because a model screen would send the secret to the model in order to find it.
- **A live view of the headless browser** replaced the screenshot-only viewer (the User asked to see it work); view-only, so no clicks reach the assistant's browser.
- **Failures are plain lines**, and Stop ends a Run within a moment even inside a long model call.
- **Two independent security reviews** fixed real holes (a redirect hop that could carry file text into the chat's own API; a link filter that failed open).
- **The acceptance harness**: eight queries on an invented folder, one with a planted injection. Live: **8 of 8 for $0.27**.
- The page's first look ("Ink": graphite, mono run detail) was designed, then superseded on 2026-10-11.

## 2026-10-09 to 2026-10-11: any model, and a better page

- **Pydantic AI becomes the model plumbing**, adopted in slices behind the existing seams, so the strong and cheap tiers can run on any provider (OpenRouter first) ([0011](adr/0011-pydantic-ai-as-the-plumbing.md)). Web search became an ordinary capability the Gate checks and the Trace shows; a tool's schema is derived from its Action class. **The loop itself was deliberately not moved**: a library would have replaced about 20 of the Runner's 279 lines and rewritten the logic the project defends.
- **A price was wrong**: Sonnet 5 was costed at $3/$15 per million tokens, not $2/$10; the error was on the safe side, and a model with no known price now fails the Run instead of counting as free.
- **The reply streams** as it is written, not for a Run that has read a file ([0013](adr/0013-the-reply-streams.md)). The first version passed a WebSocket check and failed in the real page; it is verified in the browser now.
- **The page was rebuilt to the look of the Vercel Chatbot template** in our own CSS, keeping everything Stepout-specific ([0014](adr/0014-the-page-follows-the-vercel-chatbot-look.md)).

## 2026-10-11: names by use case

- **One language for agents.** An agent is anything that calls the Model port: the five Roles, plus Screening and the Search Summarizer (single calls outside the loop). The Roles are named by what they do: `web_research`, `web_browsing`, `local_file_finder`, `local_file_reader`. "Front door" is Screening and "hand" is retired (what a Tool runs on is its implementation). The page shows an agent as "Web Research" or "Local File Finder" and counts a Run's loop cycles as actions; chats saved with the first role ids read the same ([0010](adr/0010-one-loop-many-roles.md), [0012](adr/0012-the-front-door.md)).
- **The glossary marks what is built.** Entries for Approvals, Memory and the rest carry *(planned)*; the others are in the code.

## 2026-10-12: Memory, a Record you can manage, one retry policy

- **Memory** arrived behind the seam ADR 0003 left for it: a Persona file the User owns, History written by code from a Run (the request, the outcome, what the hands did as kinds and hosts), facts the User states extracted from their own messages by one cheap call through our Model port, and Mem0 as the primary learned store (local, telemetry off, never its own model). Commands `/remember`, `/memory`, `/forget` work in both channels; a planted injection in a page and in a file changes nothing ([0016](adr/0016-memory-on-mem0-behind-the-seam.md)).
- **One retry policy** at the Model port replaced two implicit ones: classified, bounded per call and per Run, every attempt an event, an unreadable reply repaired once, the Fetcher retried, a cut stream dropped on the page and tried again ([0015](adr/0015-one-retry-policy-at-the-model-port.md)).
- **The Record became complete and manageable:** tokens, durations and attempts on every step, a `result` event per tool (a size, never its text), a log file with ids, Runs a crash left open closed at the next start, a copy of the database before a migration, rename / search / export / delete (a purge) for chats, screenshots swept by age, a monthly spending limit, and opt-in Capture. The page gained search, rename, delete, a Memory panel and the retry and Memory lines in a run.
- **Decided:** deleting a chat purges its Ledger rows (only the User asks; the Assistant still never edits the Ledger); Mem0's extraction stays ours so every model call is metered and stoppable; OpenAI's `text-embedding-3-small` is the embedder.
- **The page now looks like ChatGPT**: a plain sheet, a quiet chat list, a borderless bubble, no assistant avatar, a pill composer centred on an empty chat, a Copy button under replies, ElevenLabs' shimmering text while it works; still plain CSS and no new dependency ([0017](adr/0017-the-page-follows-the-chatgpt-look.md), superseding 0014).
- **Agent work is drawn as assistant-ui draws it**: the plan as a checklist with a thin bar, each delegation as a task card (agent, model, time, result), each hand action inside it as a tool call that opens onto its request and result ([0018](adr/0018-agent-work-as-assistant-ui-draws-it.md)). A sun or moon in the header switches light and dark, and the choice is kept in the browser. A run counts only the tool calls you can see, and Memory's panel can edit any entry in place (a Persona line, a learned fact, an earlier task), in either store.

## Tried and dropped

| What | Why |
|---|---|
| A regex decline list in front of the model | it missed paraphrases and declined harmless requests |
| A separate Planner agent | a hand-off that loses information; the agent that sees the Findings must re-plan |
| Computer use (clicks at pixel coordinates) | the Gate cannot judge a pixel click |
| Attaching to the User's everyday Chrome | their logged-in tabs would be reachable by a page that talks the model into it |
| A model-based secret screen | it would send the secret to a model to find it, and could be talked out of it |
| The loop on Pydantic AI Agents | about 20 lines of plumbing against our own logic ([log of the decision](adr/0011-pydantic-ai-as-the-plumbing.md)) |
| Temporal for pause and resume | a server and a worker for a one-process app; revisit in V1 |
| Letting Mem0 extract facts itself (`infer=True`) | its model calls would sit outside the Ledger, the cap, Stop and the retry policy |
| Folding fact extraction into Screening's call | it would put Screening's paid eval at risk to save a tenth of a cent |
| Langfuse, OpenTelemetry or Postgres for chats and steps | prompts would leave the laptop, or a multi-service stack for one user; the Ledger already maps onto spans |
