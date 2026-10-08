"""Composition root: wiring, the receive -> read -> submit loop."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from stepout import history
from stepout.channels.cli import CliChannel
from stepout.channels.web import WebChannel
from stepout.browser import Browser
from stepout.domain import Reply, Task
from stepout.fetch import Fetcher
from stepout.files import Files
from stepout.intake import ChatReading, CommandReading, DeclinedReading, FailedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.model import AnthropicModel
from stepout.runner import Runner
from stepout.screening import HaikuScreener
from stepout.store import Store

DB_PATH = Path("data/stepout.db")
GRANTS_PATH = Path("data/config/grants.toml")  # only the User edits this
SHOTS_PATH = Path("data/runs")  # page screenshots, one folder per Run
_UNEXPECTED = "I hit an unexpected problem and could not finish. Nothing on your computer was changed. Try again; if it repeats, the details are in the terminal."


def make_browser(channel) -> Browser:
    """The Runs' browser. It sends live frames to the channel if the channel shows them (the web channel does; the terminal has none, so nothing is captured)."""
    return Browser(shots=SHOTS_PATH, on_frame=getattr(channel, "live_frame", None))


def startup_notes() -> list[str]:
    """What is not set up yet, each with its fix: said at start, and again at first use by the thing that is missing."""
    notes = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        notes.append("No ANTHROPIC_API_KEY: put it in the .env file next to the app (copy .env.example to .env and fill it in), then restart. Until then every message gets this answer.")
    if not GRANTS_PATH.exists():
        notes.append(f"No {GRANTS_PATH}: the Files agent can't see your disk. Copy grants.example.toml there to allow it.")
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


async def run(channel, intake: Intake, runner: Runner) -> None:
    async for message in channel.messages():
        cid = message.conversation_id
        try:
            reading = await intake.read(message)
            match reading:
                case DeclinedReading(reason=reason, alternative=alternative, cost_usd=cost):
                    await channel.send(Reply(text=f"{reason} {alternative}", conversation_id=cid, cost_usd=cost))
                case ChatReading(text=text, cost_usd=cost):
                    await channel.send(Reply(text=text, conversation_id=cid, cost_usd=cost))
                case FailedReading(text=text):
                    await channel.send(Reply(text=text, conversation_id=cid))
                case CommandReading(name=name):
                    await channel.send(Reply(text=f"Unknown command: /{name}", conversation_id=cid))
                case NewTask(request=request, previous=previous, cost_usd=cost):
                    task = Task(user_id=message.user_id, request=request, conversation_id=cid)
                    await runner.submit(task, previous, screening_cost=cost)
        except Exception as exc:  # one failed request (API error, bad key) must not end the session
            logging.exception("request failed")
            await channel.send(Reply(text=_UNEXPECTED, conversation_id=cid))


async def main() -> None:
    load_dotenv()
    for note in startup_notes():
        print(note)
    store = Store(DB_PATH)
    ledger = Ledger(store)
    model = AnthropicModel()
    fetcher = Fetcher()
    if "web" in sys.argv[1:]:
        # ponytail: imported here only until the UI lane's U2b (channels/web.py) is merged; then it moves to the top with WebChannel
        from stepout.channels.web import StoreHistory

        channel = WebChannel(port=web_port(), shots=SHOTS_PATH, history=StoreHistory(store))  # the channel reads history from the app's own Store
        print(f"Stepout web chat: http://127.0.0.1:{await channel.start()}  (Ctrl+C to stop)")
    else:
        channel = CliChannel()
    intake = Intake(HaikuScreener(model), ledger, lambda conversation_id: history.exchanges(store, conversation_id))
    files = Files.from_config(GRANTS_PATH)
    browser = make_browser(channel)
    saved = SavedChannel(channel, ledger)
    runner = Runner(model, fetcher, ledger, saved.send, trace=channel.trace, cancel=channel.cancel, files=files, browser=browser)
    try:
        await run(saved, intake, runner)
    finally:
        await browser.aclose()


if __name__ == "__main__":
    asyncio.run(main())
