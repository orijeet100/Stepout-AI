# Assistant

A personal assistant the User drives from a Channel. It turns Requests into Tasks, carries them out on the web and in the User's folders, asks the User only when it must, and keeps Memory so it needs the User less over time.

## Language

### People and conversation

**User**:
The person the Assistant works for. Each User has their own Grants, Memory and Budget.
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
The kind of work a Task needs — Answer (no tools), Lookup (fetch or search), Browse (a browser), or Laptop (the User's own files and folders, inside Grants).
_Avoid_: mode, workflow type

**Run**:
One attempt at carrying out a Task. A Correction or a retry starts a new Run of the same Task.
_Avoid_: execution, session, episode

**Step**:
One look–decide–act cycle inside a Run.
_Avoid_: turn, iteration

**Role**:
The part the one agent loop plays in a Run — Orchestrator (no hands; it writes a Plan, Delegates, re-plans, asks the User, reports), Direct (fetch, search), Files (finds files: names and counts, never contents), Browser (headless, read-only), or Reader (reads the contents of named files). A Role is a prompt, a tool set, a model and a Step cap.
_Avoid_: agent, sub-agent, worker

**Delegate**:
The Orchestrator's Action that hands a sub-goal to a specialist Role. One level deep: a specialist cannot Delegate.
_Avoid_: spawn, dispatch

**Finding**:
What a specialist Role hands back to the Orchestrator. Untrusted content: data only — never an instruction, never Memory, never a permission.
_Avoid_: report (a Result comes from an Action)

**Plan**:
The Orchestrator's short list of steps for a Run — each with a Role, a goal and a status. It is data, written before delegating and revised at most twice if a step fails.
_Avoid_: strategy, workflow, script

**Trace**:
The live stream of everything a Run does — Plan steps, Delegates, Findings returning, Actions, Verdicts, cost, browser screenshots — shown to the User as it happens. It is read from the Ledger.
_Avoid_: log (the Ledger is the record; the Trace is the live view of it)

**Action**:
One thing the Assistant wants to do in the world during a Step — navigate, click, type, submit, fetch, read a file, upload a file.
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
The class of an Action — Safe (read, search, summarize, draft, find or count files), Consequential (submit, send, post, apply, upload a file, move or rename files, enter Persona facts or Documents into a site), or Forbidden (payments, cancellations, deleting anything, security changes, creating accounts).
_Avoid_: severity, danger level

**Refused**:
An Action the Gate will never allow, because its Risk is Forbidden or its target is Off-limits.

**Approved site**:
A website the User has approved for Consequential Actions. The list grows only through Approvals.
_Avoid_: whitelist, trusted domain

**Untrusted content**:
Anything the Assistant reads from the web or from a file. It is data only — never an instruction, never Memory, never a permission.
_Avoid_: external input, page instructions

**Tainted**:
A Run that has read file contents. Every outward Action in it needs an Approval that shows what goes where.
_Avoid_: contaminated, dirty

**Budget**:
The limits on a Task (money, Steps, active time, files read) and on the month.
_Avoid_: quota, cap, limit

### Laptop

**Grant**:
A folder the User allows the Assistant to reach, with a Mode. Only the User creates or changes Grants; the Assistant and the model never can. A User with no Grants has no file access.
_Avoid_: permission, access rule, mount, allowlist

**Mode**:
How far a Grant reaches — metadata (names, counts, sizes, dates), read (contents too), or organize (make folders, move, rename). Each includes the ones before it.
_Avoid_: level, permission level

**Off-limits**:
Places no Grant can reach — password stores and browser profiles, key and credential files, system folders, and the Assistant's own folder.
_Avoid_: blocklist, exclusion

**Plan**:
The list of changes an organizing Task would make, shown to the User for Approval before anything moves.
_Avoid_: preview, dry run

**Undo journal**:
The record that lets the User reverse a Run's moves.
_Avoid_: backup, rollback log

### Memory

**Memory**:
What the Assistant keeps between Tasks about the User and the web: Persona, Notes and History.
_Avoid_: context, knowledge base, state

**Persona**:
Facts and preferences about the User, including where their usual Documents live, kept where the User can read and edit them.
_Avoid_: profile, user model

**Pinned**:
A Persona entry the User wrote or edited. The Assistant never overwrites it.

**Document**:
A file the Assistant uses for the User, such as a resume — found inside a Grant, or given directly.
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
The append-only record of everything that happened — Messages, Steps, Verdicts, Questions, Approvals, files opened (paths and sizes, never contents), money spent, Egress, and the Role and parent of every event. It is not Memory and the model never sees it.
_Avoid_: log, trace, audit trail

**Egress**:
Any data leaving the laptop — to the model provider or into a website.
_Avoid_: outbound data, leak
