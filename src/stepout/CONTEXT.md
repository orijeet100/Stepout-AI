# Assistant

A personal assistant the User drives from a Channel. It turns Requests into Tasks, carries them out on the web, asks the User only when it must, and keeps Memory so it needs the User less over time.

## Language

### People and conversation

**User**:
The person the Assistant works for. In V0 there is exactly one.
_Avoid_: owner, customer, account

**Channel**:
A way the User reaches the Assistant — Telegram or the web page.
_Avoid_: platform, integration, interface

**Conversation**:
The ongoing exchange between the User and the Assistant on one Channel. Replies always go back to the Conversation a Message came from.
_Avoid_: thread, chat, session

**Message**:
One unit of text and files sent in a Conversation, in either direction.
_Avoid_: update, event, chat

**Stale**:
A Message that waited long enough (the laptop was off) that the Assistant asks "still want this?" before acting on it.

### Work

**Request**:
What the User asks for in a Message, before the Assistant has accepted it.
_Avoid_: query, prompt, intent, workflow

**Declined**:
A Request the Assistant will not take on because it is out of scope; it says why and what it can do instead.
_Avoid_: rejected, refused (Refused is for Actions)

**Task**:
An accepted Request the Assistant is responsible for finishing. It ends with an Outcome.
_Avoid_: job, workflow, ticket

**Route**:
The kind of work a Task needs — Answer (no tools), Lookup (fetch or search), Browse (a browser), or Laptop (the User's own computer; unavailable in V0).
_Avoid_: mode, workflow type

**Run**:
One attempt at carrying out a Task. A Correction or a retry starts a new Run of the same Task.
_Avoid_: execution, session, episode

**Step**:
One look–decide–act cycle inside a Run.
_Avoid_: turn, iteration

**Action**:
One thing the Assistant wants to do in the world during a Step — navigate, click, type, submit, fetch.
_Avoid_: command, operation, tool call

**Outcome**:
How a Task ended — Done, Blocked, Declined, Failed, Cancelled, Expired, or Uncertain.
_Avoid_: status, result

**Uncertain**:
The Outcome when the Assistant cannot tell whether a Consequential Action happened because it was interrupted mid-Action. The User is asked to check; the Action is never repeated.
_Avoid_: unknown, partial

**Blocker**:
Something on a page the Assistant must not get past — a CAPTCHA, a 2FA code, a login wall, a bot check. The Run ends Blocked.
_Avoid_: wall, challenge, obstacle

**Correction**:
A Message saying a finished Task's Outcome was wrong. It reopens the Task with a new Run.
_Avoid_: feedback, tweak, edit

### Asking the User

**Question**:
Something the Assistant asks the User mid-Run because it needs information or help. The Run pauses until an Answer arrives.
_Avoid_: prompt, escalation, clarification

**Answer**:
The User's reply to a Question.

**Approval**:
The User's yes or no to one exact Consequential Action. It expires and covers nothing else.
_Avoid_: confirmation, permission, consent

**Pause** / **Resume**:
A Run waiting on a Question or an Approval, and continuing it from its Checkpoint. Resume never means starting over.
_Avoid_: restart, retry (those start a new Run)

**Checkpoint**:
The saved point a paused or interrupted Run resumes from.
_Avoid_: snapshot, save state

### Authority

**Gate**:
The one place that gives a Verdict on every Action. The model proposes; the Gate decides.
_Avoid_: guard, filter, middleware

**Verdict**:
The Gate's answer for an Action — Allow, Ask (needs an Approval), or Refuse.
_Avoid_: decision, result

**Risk**:
The class of an Action — Safe (read, search, summarize, draft), Consequential (submit, send, post, apply, entering Persona facts or Documents into a site), or Forbidden (payments, cancellations, deletions, security changes, creating accounts).
_Avoid_: severity, danger level

**Refused**:
An Action the Gate will never allow, because its Risk is Forbidden.

**Approved site**:
A website the User has approved for Consequential Actions. The list grows only through Approvals.
_Avoid_: whitelist, trusted domain

**Untrusted content**:
Anything the Assistant reads from the web. It is data only — never an instruction, never Memory, never a permission.
_Avoid_: external input, page instructions

**Budget**:
The limits on a Task (money, Steps, active time) and on the month.
_Avoid_: quota, cap, limit

### Memory

**Memory**:
What the Assistant keeps between Tasks about the User and the web: Persona, Notes and History.
_Avoid_: context, knowledge base, state

**Persona**:
Facts and preferences about the User, kept where the User can read and edit them.
_Avoid_: profile, user model

**Pinned**:
A Persona entry the User wrote or edited. The Assistant never overwrites it.

**Document**:
A file the User gave the Assistant on purpose, such as a resume.
_Avoid_: profile data, attachment, upload

**Note**:
Know-how the Assistant wrote about a site or a kind of Task, with Provenance and an expiry.
_Avoid_: lesson, playbook, memory item

**History**:
The record in Memory of past Tasks and their Outcomes.
_Avoid_: log (the Ledger is not Memory)

**Provenance**:
Where a piece of Memory came from. Only a User Message or the Assistant's own Run Outcome may write Memory.
_Avoid_: source

**Recollection**:
What Memory hands a Run when it starts: the Persona plus the few Notes and History that matter for this Task.
_Avoid_: retrieval, context window

**Forget**:
The User removing something from Memory.

### Record

**Ledger**:
The append-only record of everything that happened — Messages, Steps, Verdicts, Questions, Approvals, money spent and Egress. It is not Memory and the model never sees it.
_Avoid_: log, trace, audit trail

**Egress**:
Any data leaving the laptop — to the model provider or into a website.
_Avoid_: outbound data, leak
