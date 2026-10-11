---
date: 2026-10-11
kind: change
lane: main
status: accepted
title: "Slice 3: a tool's schema is derived from its Action class"
tags: [pydantic-ai, capabilities, schema]
refs: [src/stepout/capabilities/base.py, src/stepout/capabilities/browse.py, src/stepout/capabilities/fetch.py, src/stepout/capabilities/files.py, src/stepout/capabilities/read_text.py, src/stepout/capabilities/web_search.py, tests/support/echo_capability.py, tests/test_capabilities.py, docs/adr/0011-pydantic-ai-as-the-plumbing.md]
---

**What.** Slice 3 of [ADR 0011](../adr/0011-pydantic-ai-as-the-plumbing.md). Each capability kept its tool twice: a Pydantic Action class and a hand-written JSON schema that had to agree with it. The schema is now derived: `tool_from(Action, description)` in `capabilities/base.py` takes the name from `kind`, the parameters from the other fields, and marks a field with no default as required. An `X | None` field is offered as X; a constraint the model should know but a call must not be rejected for (`BrowseAction.link` is at least 1) goes in `json_schema_extra`. The five capabilities and the echo example use it. The Orchestrator's control tools and the front door's `screen` tool keep `tool_schema` (their Actions are not one field per parameter: `PlanStep` carries a status the model must not set).

**Why.** One definition per tool: a field added to an Action can no longer be missing from the schema the model sees. The ADR planned "one typed function per tool, from the library". The Action class already is the typed definition, so no library was needed; the function form belongs with the loop (slice 4), where the Action stays what the Gate, the Ledger and the Trace record.

**Alternatives.** Pydantic AI's `Tool` from a function now: it needs the loop to call it, and our Runner would still need our own schema; rejected until slice 4. Leaving the schemas hand-written: they are the repetition the slice exists to remove.

**Evidence.** Before and after, the five tool definitions were dumped and compared: identical (the one difference found, the order of `files.op`'s enum, was fixed in the Action class). Whole offline suite passes (544); new `test_a_tool_is_derived_from_its_action_class_so_the_two_cannot_disagree` pins the derivation including the "told, not enforced" constraint. No live run: the model sees byte-identical tool definitions, so nothing it receives changed.

**Not checked.** The control tools and `screen` are still written by hand; deriving them would need `PlanStep` split into what the model writes and what the Runner tracks.
