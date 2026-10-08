---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Messages keep their own id and time
tags: [messages, ids, x2]
refs: [docs/log/2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md, src/stepout/ledger.py, src/stepout/app.py, src/stepout/domain.py]
---

**What.** Ask 2 of [the UI lane's list](2026-10-08-asks-of-the-main-lane-after-u2b-cost-footer-one-id-per-messa.md). `Ledger.save_message` takes `message_id` and `at`, and `SavedChannel` passes the incoming `Message.id` and `Message.at`. For a reply, `Reply` now has its own `id` and `at` (fresh by default, like `Message`), `SavedChannel.send` saves with them, and it hands the **same `Reply` object** on to the channel, so a channel can use `reply.id` and `reply.at` for its live frame. A live message and its saved copy are now one message by construction: nothing has to look the saved copy up. (The names are `message_id`, not `id`, to keep the builtin; the UI lane never calls `save_message`.) Both new arguments default to fresh values, so the CLI and every older caller are unchanged.

**One consequence, on purpose.** A message is dated when it was **sent**, not when it was saved. The page already shows a message typed during a busy Run at that moment, so history now orders the same way: a message typed at +5 s while a Run finishes at +30 s reads *first message, second message, answer one*. To keep that safe, `conversations.updated_at` is now `MAX(updated_at, new time)`: a message dated earlier than the latest one never moves a chat's "newest" time backwards.

**Why.** Today the channel looks the saved copy of a reply up by reading the whole chat, and cannot do it for a user message at all, so the page treats history as the record and filters live messages by time. Both heuristics go once ids match.

**Alternatives.** `save_message` returning the saved event: rejected, the channel sends its live frame *before* `SavedChannel` saves a user message, so it would still need an id up front. Dating by save time (as before): rejected, it would make history disagree with the live order.

**Evidence.** Offline suite **221 passed, 1 skipped, 7 deselected** (217 before; +4 in `tests/test_history.py`): a saved message keeps the id and time it was given, and gets fresh ones otherwise; through `SavedChannel` the incoming message and a reply are saved with their own ids and times and the channel receives the very `Reply` that was saved; every `Reply` has its own id and an aware time; the busy-Run ordering above, with `updated_at` unmoved. The fake channel in the history tests now stamps a message when it is pulled (as the terminal does when it reads a line), because the old fixture built all its messages up front and so dated "pay this invoice" before the first reply existed. Not changed: `channels/web.py` (the UI lane removes its two lookups, `_saved_copy` and the history heuristic in `store.ts`, when it takes this in). Files: `src/stepout/{domain,ledger,app}.py`, `tests/test_history.py`.
