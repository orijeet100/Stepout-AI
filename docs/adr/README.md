# Decisions

An ADR records a decision that is hard to reverse, surprising, or a real trade-off. It is short, dated, and never rewritten into a different story: to change a decision, add a new ADR or an amendment line and say so in the status. Small changes are in `git log`; the story in time order is [`../history.md`](../history.md).

| # | Decision | Status |
|---|---|---|
| [0001](0001-from-scratch.md) | Build what we measure, borrow plumbing | accepted; narrowed by 0011 |
| [0002](0002-laptop-only-v0.md) | V0 runs on the laptop only; no Docker | accepted |
| [0003](0003-memory-files-first.md) | Memory: plain files first, mem0 as a measured challenger | accepted, not built |
| [0004](0004-drop-zero-model-replay.md) | Measure interventions, not zero-model replay | accepted |
| [0005](0005-two-bounded-contexts.md) | Two contexts: Assistant and Evaluation | accepted, Evaluation not built |
| [0006](0006-sqlite-for-runs-and-ledger.md) | SQLite for run state and the Ledger | accepted |
| [0007](0007-brain-and-hands.md) | Brain and hands: Actions and Results are plain data | accepted |
| [0008](0008-laptop-files-grants.md) | Laptop files: Grants, Off-limits, strict taint | accepted |
| [0009](0009-react-web-page.md) | The web page is React | accepted |
| [0010](0010-one-loop-many-roles.md) | One loop, five Roles | accepted |
| [0011](0011-pydantic-ai-as-the-plumbing.md) | Pydantic AI is the plumbing; the Gate, hands and Ledger stay ours | accepted; slices 1 to 3 done, slice 4 declined |
| [0012](0012-the-front-door.md) | The front door: one cheap call before any agent money is spent | accepted |
| [0013](0013-the-reply-streams.md) | The reply streams, but never for a Run that has read a file | accepted |
| [0014](0014-the-page-follows-the-vercel-chatbot-look.md) | The page follows the look of the Vercel Chatbot template | accepted |
