# V0 finish plan — cycles to a really good V0

Status: agreed 2026-10-08 (the User delegated the orchestration to the merge agent) · supersedes the order of work in [`README.md`](README.md) from B4 and U3 on; the lanes, ownership and merge procedure there are unchanged · decisions: [`../log/`](../log/README.md) · wire contract: [`../ui-contract.md`](../ui-contract.md)

**V0 means V0-basic plus a polished page** ([`../game-plan.md`](../game-plan.md) M1–M4): an assistant you use like an app, read-only, with the Reader. Not in it: approvals and pause/resume (B5, U6), Telegram, Memory, Evaluation.

**Budget.** At most $15 of API credit in total and $10 of it on testing. Only the merge agent spends (the lanes have no key). Spent so far: about $0.65.

## Done when (each line is checked by the merge agent, live where it says so)

1. **Run view:** a plan checklist with done-of-total, a cost meter against `cap_usd`, elapsed time, a Stop button, and every state (queued, running, done, stopped, over budget, declined, failed) with a collapsed summary once finished. Real numbers only.
2. **Live browser:** while the Browser agent works, the page shows its headless browser live, view-only ([contract](../ui-contract.md#live-view-added-2026-10-08-additive)); saved screenshots show as thumbnails with a big viewer (URL and title, previous/next, Esc, focus kept). *Live check:* open a real page and watch it.
3. **History and polish:** chats and past runs load after a restart and look like a live one; a drawer under about 900 px; light and dark; reduced motion; keyboard-only use; no console errors.
4. **Looks good:** a deliberate colour scheme in both themes (contrast checked by `npm run check:contrast`), consistent type and spacing from `tokens.css`; before/after screenshots in a log entry.
5. **Reader:** "Summarize the newest PDF in `<folder>`" and "Compare my resume in `<folder>` to the job posting at `<URL>`" work. A poisoned PDF causes zero outbound requests (test); the read limits hold (20 reads, 10 MB, 40,000 characters per file); after a read the Run reaches only sites the User named. *Live check:* both demos, on invented files.
6. **Front door stable:** the live eval passes its bars on two runs in a row (agreement at least 90%, no demo false decline, mean cost at most $0.003).
7. **Acceptance:** about eight real queries (the five demos, a follow-up, a decline, a Stop) run live; steps and cost recorded per query; the step caps and the $1 cap tuned from the data. *Live check, the cost cap of this plan.*
8. **Clean:** no stale doc (STATUS, architecture, code map, glossary, ADR index, the log's `superseded` marks), no dead code (`ponytail-audit`), tests, lint and build green, `git log` and `docs/log` tell the story.

## Cycles

| Cycle | Main lane | UI lane | Merge agent |
|---|---|---|---|
| **C1** | Front door stable (temperature 0 if the API allows it; the two rows that flip between runs). **Live frames:** `Browser(on_frame=…)` and the `app.py` wiring, with tests (real Chrome). | **U3** run view (items 1 and the states). **`GET /live/{run_id}`** in the channel and a mock that replays frames. Start on the colour scheme (item 4). | merge, checks, live check of frames on a real page |
| **C2** | **B4 Reader, part 1:** `read_text` for text and PDF, read limits, secret screening, the Reader Role. | **U4:** the live view and the screenshot viewer in the page (item 2). | merge, checks, Reader demo A live |
| **C3** | **B4, part 2:** Taint and the "no web after a read" rule, the poisoned-file test, planning order in the Orchestrator prompt, demo B. | **U5:** history and polish, responsive, light and dark, accessibility (items 3 and 4). | merge, checks, demos live |
| **C4** | **B6:** the acceptance set (merge agent runs it live), tune caps and prompts from the numbers. | fixes from the live runs; screenshots for the log. | acceptance run (item 7), the staleness audit (item 8), final end to end |

A cycle ends when the lane has committed and reported. The merge agent merges on a scratch `integrate` branch, runs every check, spends where the table says, fixes integration breaks it alone can see (under about 25 lines, owner idle, logged), then moves `main` and tags `sync-N`. Nothing is pushed without the User's say-so.

## Decisions already made (lanes: do not re-ask)

- **Live view replaces the screenshot-only viewer** ([log](../log/2026-10-08-a-live-headless-browser-view-replaces-the-screenshot-only-vi.md)). Thumbnails stay.
- **Colour:** keep direction C · Ink (graphite, mono, run-green) as the base and make it excellent: one accent, both themes designed, not inverted. The UI lane may use its UI/UX Pro Max skill.
- **PDF library: `pypdf`** (BSD-3-Clause; pure Python). Add it to `pyproject.toml` and `docs/third-party.md`.
- **Secret screening: patterns** applied to extracted text before the model sees it: private-key blocks, `sk-ant-` and `sk-` keys, AWS access key ids, GitHub and Slack tokens, JWTs, and `password`, `secret`, `token` or `api key` followed by `:` or `=` and a value. Replace with `[redacted]` and say how many in the Finding. A model-based screen is out of V0. Log it as a decision.
- **Front-door decline of a request to show a secrets file is correct** ([log](../log/2026-10-08-a-front-door-decline-of-a-request-to-show-a-secrets-file-is-.md)).
- The rest of [`main-worktree.md`](main-worktree.md) B4 and [`ui-worktree.md`](ui-worktree.md) U3–U5 stands as written.

## Rules for the lanes in the loop

1. At the start of a cycle: commit, then `git merge main`, then read this file and your lane file's section.
2. Thin vertical slices, tests green at each step, one log entry per decision or behaviour change, your STATUS section updated, commit before you report.
3. Report in a few lines: the branch tip, what passed, what you could not check. Do not archive the session.
4. Stay in your owned paths. If something needs the other lane, write it into the contract and a log entry and tell the merge agent.
