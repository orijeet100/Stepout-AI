---
date: 2026-10-10
kind: change
lane: main
status: accepted
title: "Slice 2: web search is an ordinary capability the Gate checks and the Trace shows"
tags: [pydantic-ai, search, gate, taint]
refs: [src/stepout/capabilities/web_search.py, src/stepout/search.py, src/stepout/runner.py, src/stepout/model.py, src/stepout/pydantic_model.py, src/stepout/roles.py, tests/test_search.py, tests/test_runner.py, tests/test_taint.py, docs/adr/0011-pydantic-ai-as-the-plumbing.md]
---

**What.** Slice 2 of [ADR 0011](../adr/0011-pydantic-ai-as-the-plumbing.md). `web_search` was the provider's own tool, run inside the model call: the Gate never saw it, the Trace did not show it, and "no web after a file read" was enforced a second way (the Runner zeroed `max_searches`). It is now a capability like `fetch`.
- **`WebSearch`** (`capabilities/web_search.py`): Action `{"query"}`, `reaches_web = True` (taint closes it through the Gate's one rule), `repeat_guard`, at most 3 per Run (counted in `RunState.scratch`; a fourth is not run and says so), Trace line `web_search <query>`.
- **`Searcher`** (`search.py`): the hand. One cheap-tier model call with the provider's search tool (`ModelRequest.search=True`, `max_searches=1`), reply with the findings and their links only. Its cost is charged to the Run through the new `RunContext.charge`.
- **Runner:** the `searches` counter, `max_searches` special-casing and `response.searches` bookkeeping are gone. `Runner._hands` gains `"web_search": Searcher(model)`.
- **Adapters:** `ModelRequest.search` (new) asks for the provider's search; `tools` now only ever means function tools. A provider that cannot search fails the call (`no_search`) instead of answering "from a search" it did not make.
- **Direct agent:** step cap 4 to 5 (a search is a step now: three searches and the Finding, plus one spare). Untuned.

**Why.** One rule in one place; a search the User can see and the Ledger records with its query; one less thing that is specific to Anthropic's server tool (the Searcher works with any provider whose cheap tier can search).

**Alternatives.** A third-party search API (needs a key and a bill the User does not have yet; the `Searcher` is the one place that would change). Keeping the provider tool and fixing the two enforcement sites (the Gate would still never see a search).

**Evidence.** Offline: the whole suite passes (543). New or changed tests: `test_search.py` (one search asked for and reported, empty result, a fourth search not run), `test_runner.py` (a search is a step, its own call is charged), `test_taint.py` (after a read a search is refused and no search call is made), `test_model.py` and `test_pydantic_model.py` (the provider's search only when asked for; an ordinary function tool for a Role; no search on a provider that cannot). Live on Claude (`scripts/acceptance.py --live --only m1,follow-up`): 3 of 3 passed for $0.106; two more m1 samples passed. m1 (the one query that searches): $0.068 and 8 steps once (the Orchestrator found the answer thin and re-planned to the Browser agent), then $0.046 and $0.044 in 5 steps each, against $0.050 and 3 steps on `main` (priced at the old Sonnet rate). The follow-up after a file read was refused the web in 1 step as before.

**Not checked.** The 8-step sample may be variance or may be this path: three samples are not a measurement. In all three the Direct agent asked for the same search a second time and the repeat guard stopped it (about $0.002 and a step); the same habit the guard was written for. Not run through OpenRouter (no key), and not run on the other six queries live (the offline suite covers them).
