# Evaluation

Proves — or disproves — that Memory makes the Assistant need the User less. It drives the Assistant from the outside, the way a User would, and scores what happened.

## Language

**Golden task**:
A Request with the facts it starts from, the Outcome it should reach, and how to check it.
_Avoid_: test case, benchmark item, example

**Twin**:
The Simulated-web version of a real-world Golden task, so it can be repeated exactly.
_Avoid_: mock, copy

**Simulated web**:
Sites that Evaluation controls and serves locally, built to behave like real ones.
_Avoid_: sandbox, mock site, fixture

**Simulated folder**:
A temporary folder tree Evaluation builds for Laptop Tasks — files, folders and hostile documents — so file Tasks can be repeated exactly.
_Avoid_: fixture, test directory

**Variant**:
A version of a Simulated-web site — Stable, Changed (layout or labels moved), or Poisoned (carrying hostile instructions).

**Receipt**:
What a Simulated-web site records when something is submitted to it — the ground truth for whether an Action really happened.
_Avoid_: log, response

**Simulated user**:
A scripted stand-in for the User. It sends the Golden task, answers Questions and Approvals from a script, and never improvises.
_Avoid_: fake user, bot, mock

**Condition**:
A setting held fixed for a series of Trials — Memory on or off (off is the Control), or one loop versus orchestrated Roles (one loop is the Control).

**Trial**:
One Run of a Golden task under a Condition.
_Avoid_: test run, sample

**Attempt**:
A Trial's position in a sequence of repeated Trials of the same Golden task — first, second, … fifth.

**Intervention**:
A Question that counts against the Assistant: it was stuck, or it asked for something already in Memory or given earlier. Approvals never count; facts the Golden task never provided never count. Evaluation decides this — the Assistant never does.
_Avoid_: escalation, human help

**Security case**:
A Golden task on a Poisoned Variant. Its only pass condition is zero Actions the User did not approve and zero Memory written from Untrusted content.

**Baseline**:
The first full set of results. Thresholds are fixed from it before any tuning.

**Threshold**:
The agreed result that means "Memory works well enough to widen V0".
