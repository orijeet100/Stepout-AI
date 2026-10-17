# Third-party agent skills and tools

Skills are instructions that steer the agent, so each was read or scanned before it was installed, and only what we use was added (every skill's description sits in context each session).

## Installed

| What | Source | Version | Licence | Where |
|---|---|---|---|---|
| 5 skills: `api-and-interface-design`, `security-and-hardening`, `incremental-implementation`, `context-engineering`, `source-driven-development` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | commit `1401c8b` (2026-10-03) | MIT — copy in `.claude/skills/agent-skills-LICENSE` | `.claude/skills/<name>/` |
| Graphify (CLI + `/graphify` skill) | [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), PyPI package `graphifyy` (double y) | 0.9.80 | Apache-2.0 | CLI: `uv tool install "graphifyy==0.9.80"` (isolated env); skill: `.claude/skills/graphify/` (gitignored — regenerate with `graphify install --project`) |

**Review notes.** agent-skills: frontmatter is `name` and `description` only (no tool permissions), no scripts or hooks were copied, and a scan for shell-pipe, exfiltration and prompt-override patterns found only the skills' own defensive rules. Graphify: the PyPI project links to the GitHub repo, no telemetry (query logging is off unless enabled), outbound network only for SSRF-guarded URL ingest and the model calls you configure. `graphify update .` is local AST-only (no model calls); `/graphify` on docs, PDFs or images uses a model and costs money.

**Deliberately not enabled.** `graphify install --project` also registers PreToolUse hooks (a process per search/read) and a root `CLAUDE.md` rule to rebuild the graph after every code change. We removed both: too much overhead for a repo this small. To turn them on later, run `graphify claude install`.

## Runtime libraries added for a feature

| What | Source | Version | Licence | Where |
|---|---|---|---|---|
| pypdf: text from PDFs, for the Reader | [py-pdf/pypdf](https://github.com/py-pdf/pypdf), PyPI `pypdf` | 6.19.0 (`pypdf>=6.19`) | BSD-3-Clause (read from the package's own metadata); pure Python, no dependencies | `pyproject.toml`; used only in `src/stepout/reader.py` |
| Pydantic AI (slim): the model layer under any provider, for OpenRouter and other models | [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai), PyPI `pydantic-ai-slim` with extras `anthropic` and `openai` | 2.54.0 (`>=2.54,<3`) | MIT (read from the package metadata); `openai` 3.27 is Apache-2.0, `genai-prices` 0.1.10 (its price table) is MIT | `pyproject.toml`; used in `src/stepout/pydantic_model.py` |
| Mem0 (`mem0ai`): the learned-memory store, with a local vector store | [mem0ai/mem0](https://github.com/mem0ai/mem0), PyPI `mem0ai` | 2.2.1 (pinned `==2.2.1`) | Apache-2.0 (read from the package metadata) | `pyproject.toml`, optional extra `mem0` (in `[dev]`); used only in `src/stepout/memory/mem0.py`, telemetry off, never its own model ([ADR 0016](adr/0016-memory-on-mem0-behind-the-seam.md)) |
| segno: QR codes for `stepout remote` | [heuer/segno](https://github.com/heuer/segno), PyPI `segno` | 1.6.6 (`segno>=1.6`) | BSD-3-Clause (the package's LICENSE file); pure Python, no dependencies | `pyproject.toml`; used only in `src/stepout/remote.py` |

**Review notes.** Pydantic AI ([ADR 0011](adr/0011-pydantic-ai-as-the-plumbing.md)): a well-known maintained library (the Pydantic team); it releases several times a week and moved from 1.x to 2.x within a year, so it is pinned `>=2.54,<3` and adopted one slice at a time. It only talks to the providers we configure; OpenTelemetry output is off unless instrumentation is switched on. Prices for a re-pointed model come from `genai-prices`, a bundled table, so they can lag a provider's list price: an unknown model fails the Run rather than counting as free.

**Review notes.** pypdf parses files written by anyone, so it runs in a worker thread with a time limit, after a 10 MB file budget and a page cap, and extraction of a page is skipped if its decompressed content is huge (the library's own docs warn that extraction needs memory for the whole content stream). pypdf also enforces its own per-stream limits (75 MB by default). Not verified: how to tighten those limits per reader (`pypdf.Configuration` exists, but the page that should document it was not found, so the defaults are used).

## Tools the install and phone path rely on (none is shipped in the wheel)

| What | Source | Version seen | Licence | Used for |
|---|---|---|---|---|
| uv | [astral-sh/uv](https://github.com/astral-sh/uv); `winget install astral-sh.uv` | 0.12.5 here (winget lists 0.13.1) | Apache-2.0 or MIT (winget's listing) | the one install tool, `uv tool install`, and the Python it brings ([ADR 0019](adr/0019-one-command-install.md)) |
| winget | Microsoft's Windows Package Manager, part of Windows 10 and 11 (App Installer) | n/a | n/a | `stepout remote` offers to install Tailscale with it (id `Tailscale.Tailscale`, exact case) |
| Tailscale (client and service) | [tailscale.com](https://tailscale.com); client [tailscale/tailscale](https://github.com/tailscale/tailscale) | 1.104.1 (winget's listing, 2026-10-16) | client: BSD-3-Clause (winget's listing). The coordination service is Tailscale's hosted service under its own terms, with a free personal plan when this was set up (2026-10-12; not re-checked) | `stepout remote`: Serve gives the laptop an HTTPS name that only the owner's devices reach ([ADR 0020](adr/0020-phone-access-through-tailscale-serve.md)); Funnel (the public internet) is never used |
| Node.js | [nodejs.org](https://nodejs.org); `winget install OpenJS.NodeJS.LTS` | 24.20.0 (winget's LTS listing) | MIT (winget's listing) | building the page, in CI and in a source checkout only; a user of the wheel does not need it |
| pywinpty | PyPI `pywinpty` | 3.1.0 | MIT (the package's classifier) | `scripts/first_run_console.py` only, fetched by `uv run --no-project --with pywinpty`; not a dependency of the project |

## Designs the page follows (no code copied)

| What | Source | How it was used |
|---|---|---|
| The page's look | [ChatGPT](https://chatgpt.com) | colours, sizes and layout measured and written as our own tokens and CSS ([ADR 0017](adr/0017-the-page-follows-the-chatgpt-look.md)) |
| Shimmering text | [ElevenLabs UI](https://ui.elevenlabs.io/docs/components/shimmering-text) | the sweep redone as a CSS background; no motion library |
| Agent Tool, Agent plan, Subagent list, Task card | [assistant-ui](https://www.assistant-ui.com/elements/agent-plan) | markup and measured sizes ported to our CSS; no runtime, toolkit or Tailwind ([ADR 0018](adr/0018-agent-work-as-assistant-ui-draws-it.md)) |
| Icon shapes | [Lucide](https://lucide.dev) (ISC) | SVG paths in `web/src/Icon.tsx` |

## Left out of agent-skills, and why

- **Overlaps what we already have:** test-driven-development (`mattpocock-skills:tdd`), code-review-and-quality (`/code-review`), debugging-and-error-recovery (`diagnosing-bugs`), code-simplification (`/simplify`, ponytail), planning-and-task-breakdown / spec-driven-development / idea-refine / interview-me (`ce:plan`, `ce:brainstorm`, grilling), git-workflow-and-versioning (built in), documentation-and-adrs (we already write ADRs).
- **Not relevant yet:** ci-cd-and-automation, shipping-and-launch, deprecation-and-migration, performance-optimization, browser-testing-with-devtools (needs the Chrome DevTools MCP), frontend-ui-engineering.
- **Maybe later:** observability-and-instrumentation (when the Trace grows), doubt-driven-development, constraint-driven-development, using-agent-skills (a router Claude Code does not need).

To add one: copy `skills/<name>/` from a commit of that repo you have read.
