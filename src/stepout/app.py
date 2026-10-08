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
from stepout.intake import ChatReading, CommandReading, DeclinedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.model import AnthropicModel
from stepout.runner import Runner
from stepout.screening import HaikuScreener
from stepout.store import Store

DB_PATH = Path("data/stepout.db")
GRANTS_PATH = Path("data/config/grants.toml")  # only the User edits this
SHOTS_PATH = Path("data/runs")  # page screenshots, one folder per Run


def web_port() -> int:
    """The web chat's port: STEPOUT_PORT if set, else 8765 (so two checkouts can run side by side)."""
    return int(os.environ.get("STEPOUT_PORT", "8765"))


class SavedChannel:
    """A Channel whose every incoming message and every reply is also saved as chat history (v0: text only)."""

    def __init__(self, channel, ledger: Ledger) -> None:
        self._channel, self._ledger = channel, ledger

    async def messages(self):
        async for message in self._channel.messages():
            self._ledger.save_message(message.conversation_id, "user", message.text)
            yield message

    async def send(self, reply: Reply) -> None:
        self._ledger.save_message(reply.conversation_id, "assistant", reply.text, reply.run_id, reply.cost_usd)  # saved first: a closed page must not lose it
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
                case CommandReading(name=name):
                    await channel.send(Reply(text=f"Unknown command: /{name}", conversation_id=cid))
                case NewTask(request=request, previous=previous, cost_usd=cost):
                    task = Task(user_id=message.user_id, request=request, conversation_id=cid)
                    await runner.submit(task, previous, screening_cost=cost)
        except Exception as exc:  # one failed request (API error, bad key) must not end the session
            logging.exception("request failed")
            await channel.send(Reply(text=f"Something went wrong ({type(exc).__name__}). Check the terminal for details.", conversation_id=cid))


async def main() -> None:
    load_dotenv()
    store = Store(DB_PATH)
    ledger = Ledger(store)
    model = AnthropicModel()
    fetcher = Fetcher()
    if "web" in sys.argv[1:]:
        channel = WebChannel(port=web_port(), shots=SHOTS_PATH)
        print(f"Stepout web chat: http://127.0.0.1:{await channel.start()}  (Ctrl+C to stop)")
    else:
        channel = CliChannel()
    intake = Intake(HaikuScreener(model), ledger, lambda conversation_id: history.exchanges(store, conversation_id))
    if not GRANTS_PATH.exists():
        print(f"No {GRANTS_PATH}: the Files agent can't see your disk. Copy grants.example.toml there to allow it.")
    files = Files.from_config(GRANTS_PATH)
    browser = Browser(shots=SHOTS_PATH)
    saved = SavedChannel(channel, ledger)
    runner = Runner(model, fetcher, ledger, saved.send, trace=channel.trace, cancel=channel.cancel, files=files, browser=browser)
    try:
        await run(saved, intake, runner)
    finally:
        await browser.aclose()


if __name__ == "__main__":
    asyncio.run(main())
