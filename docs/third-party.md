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

**Review notes.** pypdf parses files written by anyone, so it runs in a worker thread with a time limit, after a 10 MB file budget and a page cap, and extraction of a page is skipped if its decompressed content is huge (the library's own docs warn that extraction needs memory for the whole content stream). pypdf also enforces its own per-stream limits (75 MB by default). Not verified: how to tighten those limits per reader (`pypdf.Configuration` exists, but the page that should document it was not found, so the defaults are used).

## Left out of agent-skills, and why

- **Overlaps what we already have:** test-driven-development (`mattpocock-skills:tdd`), code-review-and-quality (`/code-review`), debugging-and-error-recovery (`diagnosing-bugs`), code-simplification (`/simplify`, ponytail), planning-and-task-breakdown / spec-driven-development / idea-refine / interview-me (`ce:plan`, `ce:brainstorm`, grilling), git-workflow-and-versioning (built in), documentation-and-adrs (we already write ADRs).
- **Not relevant yet:** ci-cd-and-automation, shipping-and-launch, deprecation-and-migration, performance-optimization, browser-testing-with-devtools (needs the Chrome DevTools MCP), frontend-ui-engineering.
- **Maybe later:** observability-and-instrumentation (when the Trace grows), doubt-driven-development, constraint-driven-development, using-agent-skills (a router Claude Code does not need).

To add one: copy `skills/<name>/` from a commit of that repo you have read.
