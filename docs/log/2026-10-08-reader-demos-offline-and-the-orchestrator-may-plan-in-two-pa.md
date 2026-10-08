---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Reader demos offline, and the Orchestrator may plan in two parts
tags: [reader, demos, prompt]
refs: [docs/plan/v0-finish.md, docs/game-plan.md, src/stepout/roles.py, tests/test_reader_demos.py]
---

**What.** Cycle C2, slice 5: the two Reader demos run offline end to end, and writing them showed one prompt change was needed.
1. **Demo A, "Summarize the newest PDF in `<folder>`"** and **Demo B, "Compare my resume in `<folder>` to the job posting at `<URL>`"**, as tests with a scripted model playing the Orchestrator and the specialists and everything else real: a real `Files` hand over a real folder of invented names, real PDFs generated in the test and read by the real pypdf, the real Gate, Runner and Reader. Invented paths and files only; nothing binary is committed.
2. **The prompt change.** The Reader needs the exact path of its file, but in both demos the path exists only after the Files step has found it, and specialists see only their goal. The Orchestrator prompt said "Re-plan only if a step failed", which would push a real model to plan a Reader step with no path. It now says: *re-plan if a step failed, or when the next step needs something an earlier Finding will tell you, such as the path of a file for the reader: plan the first part, then plan the rest once its Finding is in (you can plan up to three times).* The cap is the existing `_MAX_PLANS` (the first plan plus two re-plans); Demo B uses all three.

**What the tests pin.** Demo A: the real `find` lists `new-report.pdf` before `old-report.pdf` (newest first by modification time) and leaves the `.txt` out; the Orchestrator re-plans with the path from that Finding; the Reader sees both pages of the newest PDF and nothing of the older one; the Run's steps are exactly plan, files, answer, plan, read_text, answer, answer, with nothing refused. Demo B: the Browser opens the posting **first** (allowed: nothing has been read), then the Files agent finds the resume, then the Reader reads it **last**; the browser is opened once, the Reader sees the whole resume, the Orchestrator holds both Findings when it answers, and no step is refused. And the wrong order: a Run that reads the resume first has its later `browse` refused by the Gate, the page is never opened, and the Orchestrator's answer says it could not open the posting.

**Not verified.** How a real model plans these. The scripted model makes the decisions the prompt asks for; whether Sonnet writes a first plan, waits for the path and re-plans, and puts the reading last, is the live check (the merge agent's). If it pre-plans a path-less Reader step, the Reader will report `Denied` or ask for the path, which is safe but unhelpful, and the prompt wording is the first thing to tune.

**Alternatives.** Letting the Reader see earlier Findings so a single plan would do: it would put web text and the Files listing into the one Role that opens files, against the rule that specialists see only their goal. Letting the Reader search a folder itself: it would need `files`, and the Role that opens files should hold nothing else.

**Evidence.** Offline suite **346 passed, 7 deselected** (342 before; +4 in `tests/test_reader_demos.py`). The prompt sentence is checked by a test.
