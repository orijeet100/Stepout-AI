---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Merge fix: temperature travels in the request body (SDK 1.x has no temperature argument)
tags: [merge,screening,sdk]
refs: [src/stepout/model.py, tests/test_screening.py, docs/log/2026-10-08-front-door-stability-temperature-0-and-missing-input-is-not-.md]
---

**What.** `AnthropicModel.call` sent the screening call's temperature as `messages.create(temperature=0.0)`. The installed SDK (`anthropic` 1.12.0, also the Main lane's own venv) has no `temperature` argument on `create()` any more, so every real screening raised `TypeError: AsyncMessages.create() got an unexpected keyword argument 'temperature'`; the live eval failed on its first row and, in the app, every message would have taken the fail-open path (proceed with the last three exchanges) and logged an error. It now goes in the request body: `extra_body={"temperature": …}`, which every SDK version accepts. The offline test that should have caught this used a fake client that accepts any keyword; it is replaced by `test_temperature_reaches_the_wire_through_the_real_sdk_only_when_asked_for`, which drives the real `anthropic.AsyncAnthropic` over a mock HTTP transport (no network) and reads the JSON body.

**Why.** Found by the merge agent's live eval at cycle C1, the first run that touched the real SDK. A fake that is looser than the thing it stands for hides exactly this; the new test goes through the real client.

**Alternatives.** Pin the SDK below 1.0: it would keep an old argument that the newer API rejects for newer models, and trade one drift for another. Drop temperature 0: the two-run check below shows it makes the front door repeatable.

**Evidence.** The new test fails on the old call site and passes on the fix (`pytest tests/test_screening.py`: 39 passed). Live, two eval runs in a row after the fix: 97% agreement (bar 90%), mean cost $0.0019 (bar $0.003), no demo false decline, no fallback, and the same result row for row (temperature 0 holds). Two ordinary rows are declined both times with a polite request for the missing input ("Share the list with me, and I'll remove the duplicate lines"): the outcome for the User is the same as proceeding, so they stay as labeled and the bars hold.
