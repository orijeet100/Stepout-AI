---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Stop ends a Run within a moment, even inside a long model call, read, walk or page load
tags: [stop, runner, c4]
refs: [src/stepout/runner.py, tests/test_stop.py]
---

**What.** Cycle C4, slice 3, from the merge agent. Stop was a flag the Runner looked at *between* steps (and the Files walk looked at inside a walk). So a model call that took 20 s (a long web search), a read of a big PDF (up to the 30 s limit), a page that would not load, or any hand that does not look at the flag, made the button wait for it. Now `Runner._unless_stopped` awaits the model call or the hand together with the Stop flag and gives up on whatever is slower the moment the flag is set: the Run ends at once with "Stopped by you.", the row is `cancelled` (the contract's `stopped`), and the Run's browser context is closed as before. Every model call and every hand call goes through it, so a hand added later is covered without knowing about Stop.

**What it cannot do.** A worker thread cannot be killed. A read (`asyncio.to_thread` into pypdf) or a files walk that is already running keeps running in the background until it returns (a walk looks at the flag and stops itself within a directory; a pypdf parse is bounded by the 30 s limit and the page and stream caps). The Run does not wait for it. A page load is abandoned by closing the Run's context.

**What was already right.** A Stop between steps (unchanged), and a stale Stop from before a request being cleared when the Run starts (an existing test). A Stop pressed while the front door is still thinking, before a Run exists, is lost: there is nothing yet to stop, and the reply that follows is a Run the User can stop.

**Alternatives.** Passing the flag into every hand so each checks it: three of four hands cannot check inside a library call (pypdf, Playwright, the model SDK). Cancelling the Run's whole task from the channel: it would skip the `finally` that records the outcome unless every await was made cancel-safe. Racing at the one place every slow thing is awaited was the smaller change.

**Evidence.** `tests/test_stop.py` (7): Stop during a hand that takes 30 s and ignores the flag, standing in for a long read, a long walk and a page that will not load, and during a model call that takes 30 s: each ends within a moment (under 3 s allowed, well under 1 s measured), the reply is "Stopped by you.", the row is `cancelled`, and the browser session is closed; a walk that does honour the flag still ends `cancelled`, not `failed`; the real `Reader` with its real worker thread is abandoned at once (the thread keeps running 1.5 s, the Run does not); and **a real headless Chrome** loading a page that answers only when the test lets it ends within 5 s of Stop with its context closed. No asyncio "never awaited" or "pending task" warnings under `-X dev`. Mutation-checked: not racing the hands, not racing the model call, and the race that never stops each fail a test. File: `src/stepout/runner.py`.
