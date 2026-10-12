# 0015 — One retry policy, owned by the Model port

Status: accepted · 2026-10-12

**Decision.** Every model call (the Runner's loop, Screening, the Searcher) goes through one `RetryingModel` wrapper (`src/stepout/retry.py`) built once at the composition root. The provider SDKs' own retries are switched off (`max_retries=0` on the Anthropic client; the same setting on the client behind a Pydantic AI model), so there is exactly one policy and every attempt is ours to record and bound.

**Why.** Before this, the Anthropic adapter retried on the SDK's defaults, the Pydantic AI adapter on whatever its provider SDK did, nothing recorded either, and a failed attempt's cost was not counted against the $1 cap. A policy that differs by adapter, cannot be seen and is not bounded is not a policy. Alternatives: a retry loop in the Runner (Screening and the Searcher would need a second copy) or one inside each adapter (two copies that drift).

**The policy** is a table keyed by `Failure.kind` (`retry.py`, starting values to calibrate): the transient kinds (`rate_limit`, `overloaded`, `server_error`, `timeout`, `connection`) get three attempts with exponential backoff and jitter, or the provider's `Retry-After` when it gave one (a wait over 30 s is not taken: the User is told how long it is); every other kind, and every kind not in the table, is tried once. A stream cut after words reached the page gets one more try after the page is told to drop them (`reset`). A reply that cannot be read gets one repair per call (three per Run): it is asked again with the field and the rule that failed, never the value, and an unreadable reply that was billed is counted. Per Run: at most 8 retries and 60 s of waiting, and no retry once the budget is used up. A read-only tool is retried once for a timeout, a dropped connection, 429 or 5xx (only the Fetcher today); nothing that changes something will ever be retried: its outcome is then unknown and the User is asked.

**What it needs from the rest.** A per-Run scope (`scope.py`, a context variable) gives the wrapper the Run's Trace, its budget and the page's `reset`; a call outside a Run (Screening) gets the same attempts and waits and is only logged. Stop needs nothing: the Runner awaits the call through `_unless_stopped`, so a cancel ends a wait where it is.

**Amends [0013](0013-the-reply-streams.md):** a connection that drops mid-reply no longer leaves its words on the page; the page is told to drop them and the reply is tried again.

**Limits.** A provider whose client has no `max_retries` setting (Google's, Bedrock's) keeps its own retries; a request-level test counts attempts for the adapters that matter. A cut stream is charged an estimate of its input (about four characters a token): the provider's billing of a cut stream is not known. Mem0's internal embedding client keeps its own retries (see [0016](0016-memory-on-mem0-behind-the-seam.md) once written).
