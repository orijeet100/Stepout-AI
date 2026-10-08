---
date: 2026-10-07
kind: change
lane: main
status: accepted
title: B2 v0 save chats
tags: [store, history, persistence]
refs: [docs/plan/main-worktree.md, src/stepout/history.py, src/stepout/migrations/0003_conversations.sql, tests/test_history.py]
---

**What.** The smallest slice of B2: chats are saved and can be read back. Migration `0003_conversations.sql` adds a `conversations` table (`id`, `title`, `created_at`, `updated_at`) and `events.conversation_id` (indexed). `Message`, `Reply`, `Task` and `Event` carry a `conversation_id` (default `"default"`, so the CLI and the page, which send no chat id yet, share one chat). Every event the Runner and Intake write is stamped with its chat. `app.SavedChannel` wraps any Channel: each incoming message and each reply is saved by `Ledger.save_message` as an event of kind `message` (`data`: `role`, `text`); a chat is created by its first message and titled by it, cut to 60 characters. `history.py` (read-only) has `list_conversations(store)` (newest first) and `get_conversation(store, id)` (messages in order), both returning plain dicts.

**Why.** The User asked for a very v0 where chats are "just saved"; chat history lived in the page server's memory and was gone on restart. This is also the base the page's history list (U5) and the front door (B3) read from.

**Alternatives.** Not in this slice, still B2: the `tasks` and `runs` rows, `contract.py` and its fixture test, the screenshot `url` and `title`, `cost_usd` on the reply and dropping the cost footer, a `run_events` reader, a queued/running `state`. Recording in `Runner` and `Intake` separately was rejected for one wrapper that sees every message and reply. Deliberately loose for v0 (the User said insecure is fine): no ids are validated (queries are parameterised, so nothing is injectable), the page's `channels/web.py` is untouched so it still replays its own in-memory history and sends no chat id, and the migration race noted in STATUS is not fixed.

**Evidence.** Offline suite **155 passed, 6 deselected** (152 before; +3 in `tests/test_history.py`), all older tests unedited. Tests: a 0002 database upgrades to 0003 keeping its events (user_version 3, old events in no chat); saved messages come back in order from a new `Store` on the same file, newest chat first, titles cut to 60, unknown id gives `None`, chats stay apart; a scripted session over two chats (an answer, a decline, an answer) survives reopening the file, each reply returns to its own chat, and no event has a NULL chat id. By hand: the real `python -m stepout.app` (CLI, real file database, a decline and an unknown command, no API call) saved the chat, and a separate process read it back: 4 messages in order. Files: `src/stepout/{migrations/0003_conversations.sql,domain,ledger,history,intake,runner,app}.py`, `tests/test_history.py`. Not verified: the web page (it neither sends nor reads chat ids yet).
