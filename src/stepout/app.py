"""Composition root: wiring, the receive -> read -> submit loop."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from stepout import capture as capture_mod
from stepout import commands, history, housekeeping, logs
from stepout import memory as memory_mod
from stepout.chats import ChatKeeper
from stepout.channels.cli import CliChannel
from stepout.channels.web import StoreHistory, WebChannel
from stepout.browser import Browser
from stepout.domain import Reply, Task
from stepout.extract import Extractor, Learner
from stepout.failure import UNEXPECTED
from stepout.fetch import Fetcher
from stepout.files import Files
from stepout.intake import ChatReading, CommandReading, DeclinedReading, FailedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.pydantic_model import PydanticModel, default_model
from stepout.retry import RetryingModel
from stepout.roles import HAIKU, SONNET
from stepout.runner import Runner
from stepout.screening import HaikuScreener
from stepout.store import Store

DB_PATH = Path("data/stepout.db")
GRANTS_PATH = Path("data/config/grants.toml")  # only the User edits this
SHOTS_PATH = Path("data/runs")  # page screenshots, one folder per Run
LOGS_PATH = Path("data/logs")  # the app log (logs.py)
MEMORY_PATH = Path("data/memory")  # Persona and what was learned (memory.py)
CAPTURE_PATH = Path("data/capture")  # prompts and replies, only when STEPOUT_CAPTURE=1 (capture.py)


def make_browser(channel) -> Browser:
    """The Runs' browser. It sends live frames to the channel if the channel shows them (the web channel does; the terminal has none, so nothing is captured)."""
    return Browser(shots=SHOTS_PATH, on_frame=getattr(channel, "live_frame", None))


def startup_notes(keys: Sequence[str] = ("ANTHROPIC_API_KEY",)) -> list[str]:
    """What is not set up yet, each with its fix: said at start, and again at first use by the thing that is missing. `keys`: the provider keys the chosen models need."""
    notes = []
    for var in keys:
        if not os.environ.get(var):
            notes.append(f"No {var}: put it in the .env file next to the app (copy .env.example to .env and fill it in), then restart. Until then every message gets this answer.")
    if not GRANTS_PATH.exists():
        notes.append(f"No {GRANTS_PATH}: the Local File Finder and Local File Reader agents can't see your disk. Copy grants.example.toml there to allow it.")
    return notes


def web_port() -> int:
    """The web chat's port: STEPOUT_PORT if set, else PORT (the app's preview tool assigns one when 8765 is taken), else 8765 (so two checkouts can run side by side)."""
    for name in ("STEPOUT_PORT", "PORT"):
        if (value := os.environ.get(name, "")).isdigit():  # a stray PORT that is not a number (another tool's) must not crash the start
            return int(value)
    return 8765


class SavedChannel:
    """A Channel whose every incoming message and every reply is also saved as chat history (v0: text only)."""

    def __init__(self, channel, ledger: Ledger) -> None:
        self._channel, self._ledger = channel, ledger

    async def messages(self):
        async for message in self._channel.messages():
            self._ledger.save_message(message.conversation_id, "user", message.text, message_id=message.id, at=message.at)
            yield message

    async def send(self, reply: Reply) -> None:
        self._ledger.save_message(reply.conversation_id, "assistant", reply.text, reply.run_id, reply.cost_usd, message_id=reply.id, at=reply.at)  # saved first: a closed page must not lose it
        await self._channel.send(reply)


def month_cap(environ=os.environ) -> float:
    """What the app may spend in a calendar month, in dollars (STEPOUT_MONTH_CAP_USD). A starting value, not a recommendation."""
    try:
        return float(environ.get("STEPOUT_MONTH_CAP_USD", "10.00"))
    except ValueError:
        return 10.00


async def run(channel, intake: Intake, runner: Runner, month_left=None, memory=None, learner: Learner | None = None) -> None:
    """`month_left()`: dollars the month has left; at zero a message is answered with a line and costs nothing (a slash command is free and still works)."""
    async for message in channel.messages():
        cid = message.conversation_id
        try:
            if month_left is not None and not message.text.strip().startswith("/") and month_left() <= 0:
                await channel.send(Reply(text=f"This month's spending limit of ${month_cap():.2f} is used up, so I have not run anything. Raise STEPOUT_MONTH_CAP_USD in .env, or wait for next month.", conversation_id=cid))
                continue
            reading = await intake.read(message)
            match reading:
                case DeclinedReading(reason=reason, alternative=alternative, cost_usd=cost):
                    await channel.send(Reply(text=f"{reason} {alternative}", conversation_id=cid, cost_usd=cost))
                case ChatReading(text=text, cost_usd=cost):
                    await channel.send(Reply(text=text, conversation_id=cid, cost_usd=cost))
                    if learner is not None:
                        await learner.learn(message)
                case FailedReading(text=text):
                    await channel.send(Reply(text=text, conversation_id=cid))
                case CommandReading(name=name, args=args):
                    said = await commands.handle(name, args, memory) if memory is not None else None
                    await channel.send(Reply(text=said if said is not None else f"Unknown command: /{name}", conversation_id=cid))
                case NewTask(request=request, previous=previous, cost_usd=cost):
                    task = Task(user_id=message.user_id, request=request, conversation_id=cid)
                    run_id = await runner.submit(task, previous, screening_cost=cost)
                    if learner is not None:
                        await learner.learn(message, run_id)  # after the reply: what the User said about themselves, kept and shown
        except Exception:  # one failed request (API error, bad key) must not end the session
            logging.exception("request failed")
            await channel.send(Reply(text=UNEXPECTED, conversation_id=cid))


async def main() -> None:
    load_dotenv()
    log_file = logs.configure(LOGS_PATH)
    base = default_model()
    other = isinstance(base, PydanticModel)  # a tier is re-pointed in the environment (STEPOUT_STRONG_MODEL / STEPOUT_CHEAP_MODEL)
    if other:
        print(f"Models: strong = {base.target(SONNET)}, cheap = {base.target(HAIKU)}")
    logging.getLogger(__name__).info("start: log=%s models=%s", log_file, f"{base.target(SONNET)} / {base.target(HAIKU)}" if other else "anthropic default")
    for note in startup_notes(base.key_vars() if other else ("ANTHROPIC_API_KEY",)):
        print(note)
    model = RetryingModel(base)  # the one retry policy (ADR 0015), for the Runner, Screening and the Searcher alike
    store = Store(DB_PATH)
    ledger = Ledger(store)
    memory, memory_line = memory_mod.build(root=MEMORY_PATH)
    print(memory_line)
    logging.getLogger(__name__).info(memory_line)
    for folder in (SHOTS_PATH, CAPTURE_PATH):
        if (swept := housekeeping.sweep(folder, housekeeping.retention_days())):
            logging.getLogger(__name__).info("removed %d old item(s) from %s", swept, folder)
    if (cut_off := ledger.close_interrupted()):
        logging.getLogger(__name__).warning("closed %d run(s) the last session left open", cut_off)
    fetcher = Fetcher()
    if "web" in sys.argv[1:]:
        async def forget_chat(chat: str, run_ids: list[str]) -> None:
            await memory.forget_chat(chat)  # what Memory kept from a deleted chat goes with it

        async def remove_capture(chat: str, run_ids: list[str]) -> None:
            capture_mod.Capture(CAPTURE_PATH).remove(run_ids)  # a deleted chat's prompts go with it, whether or not capture is on now

        keeper = ChatKeeper(ledger, SHOTS_PATH, [forget_chat, remove_capture])
        channel = WebChannel(port=web_port(), shots=SHOTS_PATH, history=StoreHistory(store), keeper=keeper, memory=memory)  # the channel reads history from the app's own Store
        print(f"Stepout web chat: http://127.0.0.1:{await channel.start()}  (Ctrl+C to stop)")
    else:
        channel = CliChannel()
    intake = Intake(HaikuScreener(model), ledger, lambda conversation_id: history.exchanges(store, conversation_id))
    files = Files.from_config(GRANTS_PATH)
    browser = make_browser(channel)
    saved = SavedChannel(channel, ledger)
    def month_left() -> float:
        return month_cap() - ledger.month_spend()

    runner = Runner(model, fetcher, ledger, saved.send, trace=channel.trace, cancel=channel.cancel, files=files, browser=browser, month_left=month_left, memory=memory,
                    capture=capture_mod.from_env(CAPTURE_PATH))
    try:
        learner = Learner(Extractor(model), memory, ledger, trace=channel.trace)
        await run(saved, intake, runner, month_left, memory, learner)
    finally:
        await browser.aclose()


if __name__ == "__main__":
    asyncio.run(main())
