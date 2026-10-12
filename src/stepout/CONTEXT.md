# Assistant

A personal assistant the User drives from a Channel. It turns Requests into Tasks, carries them out on the web and in the User's folders, asks the User only when it must, and keeps Memory so it needs the User less over time.

## Language

Entries marked *(planned)* are not in the code yet; the rest are (checked 2026-10-12).

### People and conversation

**User**:
The person the Assistant works for. Each User has their own Grants, Memory and Budget.
_Avoid_: owner, customer, account

**Channel**:
A way the User reaches the Assistant — the web page or the terminal; Telegram is planned.
_Avoid_: platform, integration, interface

**Conversation**:
The ongoing back-and-forth between the User and the Assistant on one Channel. It holds many Tasks, and the User may keep several side by side (the page calls them chats). Replies always go back to the Conversation a Message came from.
_Avoid_: thread, session

**Message**:
One unit of text and files sent in a Conversation, in either direction.
_Avoid_: update, event, chat

**Exchange**:
A Request and the reply the User saw for it, inside one Conversation. It is Tainted if its Run was.
_Avoid_: turn, round

**Stale** *(planned)*:
A Message that waited long enough (the laptop was off) that the Assistant asks "still want this?" before acting on it.

### Work

**Request**:
What the User asks for in a Message, before the Assistant has accepted it.
_Avoid_: query, prompt, intent, workflow

**Screening**:
The check a Request passes before it becomes a Task: Proceed, Decline, or a short reply for plain chat. It runs before any Orchestrator money is spent, and also picks out which earlier Exchanges the Request relates to. The Screening agent does it with one cheap Model call.
_Avoid_: front door, moderation, guardrail, validation

**Declined**:
A Request the Assistant will not take on because it is unsafe or out of scope; it says why and what it can do instead.
_Avoid_: rejected, refused (Refused is for Actions)

**Follow-up**:
A Message that relates to earlier Exchanges in the same Conversation — not necessarily the latest. The Orchestrator is given those Exchanges, and only those. A Message that relates to none is a new Task and gets no history.
_Avoid_: reply-to, continuation, thread

**Task**:
An accepted Request the Assistant is responsible for finishing. It ends with an Outcome.
_Avoid_: job, workflow, ticket

**Run**:
One attempt at carrying out a Task. A Correction or a retry starts a new Run of the same Task.
_Avoid_: execution, session, episode

**Step**:
One item of a Plan: a Role, a goal and a status. The page counts them ("2 of 3 steps").
_Avoid_: subtask, job

**Agent**:
Anything that calls the Model port, with Tools or by passing context to or from other agents. Seven today: the five Roles (the Orchestrator and four specialists, played by the one Runner loop) and two single-call agents outside the loop, the Screening agent and the Search Summarizer. The Orchestrator is an agent like the others. Named by use case ("Local File Finder agent"), never by the Tool or implementation it uses.
_Avoid_: bot, worker, hand

**Role**:
The definition of an agent the Runner loop plays in a Run: a prompt, a tool set, a model and an Action cap. V0 has five — Orchestrator (no tools of its own: it writes a Plan, Delegates, re-plans, asks the User, reports), Web Research (`web_search`, `fetch`), Web Browsing (`browse`: headless, read-only), Local File Finder (`files`: names and counts, never contents) and Local File Reader (`read_text`: the contents of one named file). Ids in code: `orchestrator`, `web_research`, `web_browsing`, `local_file_finder`, `local_file_reader`.
_Avoid_: worker

**Specialist**:
Any Role except the Orchestrator. It sees only its own goal, holds one kind of Tool, hands back a Finding and cannot Delegate, so delegation is one level deep.
_Avoid_: sub-agent, worker

**Search Summarizer**:
The single-call agent behind the `web_search` Tool: one cheap Model call that runs the provider's own search once and reports what it found with source links. What it returns is Untrusted content; its cost is charged to the Run.
_Avoid_: searcher agent

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
One thing an agent proposes in one pass of its loop — plan, delegate, answer, or a Tool call such as fetch or read a file; later also type, submit or upload. Each gets one Verdict, and the page counts a Run's Actions ("5 actions"). A Role's Action cap is `max_steps` in code.
_Avoid_: command, operation

**Tool**:
What an agent can call — fetch, files, browse, web search, read text — kept in one file: its schema, its Action, how it runs, its own Gate rule, its Trace line and a one-line blurb of what it can and cannot do. A new Tool is one file plus one line in the registry; a Role's tools are Tool names. In code the class is `Capability` (its `tool` attribute is the schema the model sees). What a Tool runs on (Fetcher, Files, Browser, Reader, the Search Summarizer) is its implementation, never called a "hand".
_Avoid_: plugin, skill, hand

**Outcome**:
How a Task ended — Done, Failed or Cancelled; Blocked, Declined, Expired and Uncertain are planned.
_Avoid_: status, result

**Uncertain** *(planned)*:
The Outcome when the Assistant cannot tell whether a Consequential Action happened because it was interrupted mid-Action. The User is asked to check; the Action is never repeated.
_Avoid_: unknown, partial

**Blocker** *(planned)*:
Something on a page the Assistant must not get past — a CAPTCHA, a 2FA code, a login wall, a bot check. The Run ends Blocked.
_Avoid_: wall, challenge, obstacle

**Correction** *(planned)*:
A Message saying a finished Task's Outcome was wrong. It reopens the Task with a new Run.
_Avoid_: feedback, tweak, edit

### Asking the User

**Question** *(planned)*:
Something the Assistant asks the User mid-Run because it needs information or help. The Run pauses until an Answer arrives.
_Avoid_: prompt, escalation, clarification

**Answer** *(planned)*:
The User's reply to a Question.

**Approval** *(planned)*:
The User's yes or no to one exact Consequential Action. It expires and covers nothing else.
_Avoid_: confirmation, permission, consent

**Pause** / **Resume** *(planned)*:
A Run waiting on a Question or an Approval, and continuing it from its Checkpoint. Resume never means starting over.
_Avoid_: restart, retry (those start a new Run)

**Checkpoint** *(planned)*:
The saved point a paused or interrupted Run resumes from.
_Avoid_: snapshot, save state

### Authority

**Gate**:
The one place that gives a Verdict on every Action. The model proposes; the Gate decides.
_Avoid_: guard, filter, middleware

**Verdict**:
The Gate's answer for an Action — Allow, Ask (needs an Approval), or Refuse.
_Avoid_: decision, result

**Risk** *(planned)*:
The class of an Action — Safe (read, search, summarize, draft, find or count files), Consequential (submit, send, post, apply, upload a file, move or rename files, enter Persona facts or Documents into a site), or Forbidden (payments, cancellations, deleting anything, security changes, creating accounts).
_Avoid_: severity, danger level

**Refused**:
An Action the Gate will never allow, because its Risk is Forbidden or its target is Off-limits.

**Approved site** *(planned)*:
A website the User has approved for Consequential Actions. The list grows only through Approvals.
_Avoid_: whitelist, trusted domain

**Untrusted content**:
Anything the Assistant reads from the web or from a file. It is data only — never an instruction, never Memory, never a permission.
_Avoid_: external input, page instructions

**Tainted**:
A Run that has read file contents, or that builds on an Exchange whose Run did. Every outward Action in it needs an Approval that shows what goes where. Until Approvals exist, a Tainted Run cannot reach the web at all (the Gate refuses it, and web search is not offered); only file text actually handed over taints, so a refused or empty read does not. The Exchange it leaves is marked `tainted`, so a Follow-up Screening links to it starts Tainted, and so on down the chat; a new Task linked to nothing does not.
_Avoid_: contaminated, dirty

**Budget**:
The limits on a Task (money, Actions, active time, files read) and on the month. Today only the money limit exists: the per-Run cap (`STEPOUT_TASK_CAP_USD`, `cap_usd` on the wire).
_Avoid_: quota, limit

### Laptop

**Grant**:
A folder the User allows the Assistant to reach, with a Mode. Only the User creates or changes Grants; the Assistant and the model never can. A User with no Grants has no file access.
_Avoid_: permission, access rule, mount, allowlist

**Mode**:
How far a Grant reaches — metadata (names, counts, sizes, dates), read (contents too), or organize (make folders, move, rename; planned). Each includes the ones before it.
_Avoid_: level, permission level

**Off-limits**:
Places no Grant can reach — password stores and browser profiles, key and credential files, system folders, and the Assistant's own folder.
_Avoid_: blocklist, exclusion

**Plan** *(planned)*:
The list of changes an organizing Task would make, shown to the User for Approval before anything moves.
_Avoid_: preview, dry run

**Undo journal** *(planned)*:
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
A Persona entry the User wrote or edited. Nothing but the User's own `/remember` and `/forget` touches the file; an entry's id is a hash of its text.

**Document** *(planned)*:
A file the Assistant uses for the User, such as a resume — found inside a Grant, or given directly.
_Avoid_: profile data, attachment, upload

**Note** *(planned)*:
Know-how the Assistant wrote about a site or a kind of Task, with Provenance and an expiry.
_Avoid_: lesson, playbook, memory item

**History**:
The record in Memory of past Tasks and their Outcomes. Written by code after a Run: the request, the outcome and what the hands did as kinds and hosts only; a Run that read a file keeps only the request and the outcome.
_Avoid_: log (the Ledger is not Memory)

**Provenance**:
Where a piece of Memory came from. Only a User Message or the Assistant's own Run Outcome may write Memory.
_Avoid_: source

**Recollection**:
What Memory hands a Run when it starts: the Persona plus the few learned facts and History that matter for this Task, about 2,000 characters at most, shown to the Orchestrator only, as data about the User and never as instructions or permission.
_Avoid_: retrieval, context window

**Forget**:
The User removing something from Memory with `/forget <id>`, or deleting the chat it came from. It never edits the Ledger.

### Record

**Ledger**:
The record of everything that happened, append-only for the Assistant (it never edits or deletes a row; only the User deletes, and then a whole chat, with everything about it) — Messages, Steps, Verdicts, Questions, Approvals, files opened (paths and sizes, never contents), money spent, Egress, and the Role and parent of every event. It is not Memory and the model never sees it.
_Avoid_: log, trace, audit trail

**Egress** *(planned)*:
Any data leaving the laptop — to the model provider or into a website.
_Avoid_: outbound data, leak
