---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Failures the User can read: a model or hand that fails ends the Run cleanly with a plain line
tags: [failure, api, errors, c4]
refs: [src/stepout/failure.py, src/stepout/model.py, src/stepout/runner.py, src/stepout/intake.py, src/stepout/app.py, tests/test_failures.py]
---

**What.** Cycle C4, slice 1, from the merge agent: what a real user meets that a scripted model never shows. Before, any exception out of a model call or a hand went up to `app.run`, which said "Something went wrong (TypeError). Check the terminal", and the Ledger kept no cause.
- **`Failure(kind, message, status)`** (`failure.py`): a failure the User can be told about in a line. `AnthropicModel` turns every API error into one (`_explain`): 401/403 `auth` ("Anthropic rejected the API key (401). Check ANTHROPIC_API_KEY in the .env file, then restart the app."), 429 `rate_limit`, 529 `overloaded` ("Wait a minute, then send it again."), 5xx `server_error`, a timeout, no network (`connection`), a 400 "credit balance is too low" (`credit`: "Your Anthropic account is out of credit. Add credit at console.anthropic.com"), and any other rejection. A reply the SDK let through that is not a message (not JSON, `{}`, a tool call missing its arguments) is `malformed`: "Anthropic's reply could not be understood". No key at all is `no_key`, checked before any request (the SDK would only fail later with a TypeError).
- **The Run** (`Runner.submit`): any exception from the Orchestrator or a specialist ends the Run `failed` (the row keeps the cost of the calls that worked; a failed call costs nothing), emits an **`error` event** (`cause`, the exception class as `type`, `status` if any, under the Role that was acting) and replies with the plain line. A `Failure` says its own line; anything else says "I hit an unexpected problem and had to stop this task. Nothing on your computer was changed. Try again; if it repeats, the details are in the terminal." and the terminal gets the traceback. The browser session is closed as before. The app answers the next message. An answer that comes back empty is no longer an empty reply ("I finished without an answer to give you").
- **The front door** still fails open for a rate limit, an overload, a server error, a timeout or a malformed reply (the message goes through, `screening_fallback` is recorded). A **bad key, no key or no credit at the front door** does not: the Run's own calls would fail the same way, so it says so in one reply and starts no Run (`FailedReading`, a `screening_failed` event). It is said for each message until the key is fixed, which costs nothing.
- `app.run`'s last-resort reply for anything outside a Run (a database error) uses the same unexpected-problem line, with no exception class.

**Why.** A user with a tired key, a busy API or a dropped connection must be told what to do, not shown a type name; and the Ledger has to say why a Run failed (the acceptance harness reports it).

**Alternatives.** Retrying inside the app: the SDK already retries 429, 5xx and timeouts twice with backoff; a third layer would hide the failure and burn the User's time. A new Outcome for "failed because of the API": the row says `failed`, the event says why. Putting the explanations in the page: out of scope and the page would need the cause; the line is the reply.

**Evidence.** `tests/test_failures.py` (29): the real anthropic client over a mock HTTP transport (no network) returning 429, 529, 500, 401, a timeout, no network, a body that is not JSON, `{}`, a tool call with no arguments and an out-of-credit 400, each at the Orchestrator and at a specialist: one plain reply with no stack trace or exception name, the Run `failed` with the cost of what worked, the `error` event with the cause, and the next message served; a 401 at the front door says so and starts no Run; the other front-door failures fail open; no key at all; an empty answer; a hand that raises. Mutation-checked: the Run not catching, the front door failing open on a bad key, no key check, malformed replies not wrapped, and the cause not recorded each fail a test. The three older tests that expected an exception to escape the Run now expect a failed Run and a plain reply. Fake SDK clients in the tests gained `api_key` (the real client has it). Files: `src/stepout/{failure,model,runner,intake,app}.py`.

**Not checked.** Real API failures (a real 529 is rare; the transport returns the documented shapes). The wording is the first thing to tune with a real user.
