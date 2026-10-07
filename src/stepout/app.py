"""Composition root: wiring, the receive -> read -> submit loop."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from stepout.channels.cli import CliChannel
from stepout.channels.web import WebChannel
from stepout.domain import Reply, Task
from stepout.fetch import Fetcher
from stepout.intake import CommandReading, DeclinedReading, Intake, NewTask
from stepout.ledger import Ledger
from stepout.model import AnthropicModel
from stepout.runner import Runner
from stepout.store import Store

DB_PATH = Path("data/stepout.db")


async def run(channel, intake: Intake, runner: Runner) -> None:
    async for message in channel.messages():
        try:
            reading = await intake.read(message)
            match reading:
                case DeclinedReading(reason=reason, alternative=alternative):
                    await channel.send(Reply(text=f"{reason} {alternative}"))
                case CommandReading(name=name):
                    await channel.send(Reply(text=f"Unknown command: /{name}"))
                case NewTask(request=request, route=route):
                    task = Task(user_id=message.user_id, request=request, route=route)
                    await runner.submit(task)
        except Exception as exc:  # one failed request (API error, bad key) must not end the session
            logging.exception("request failed")
            await channel.send(Reply(text=f"Something went wrong ({type(exc).__name__}). Check the terminal for details."))


async def main() -> None:
    load_dotenv()
    store = Store(DB_PATH)
    ledger = Ledger(store)
    model = AnthropicModel()
    fetcher = Fetcher()
    if "web" in sys.argv[1:]:
        channel = WebChannel()
        print(f"Stepout web chat: http://127.0.0.1:{await channel.start()}  (Ctrl+C to stop)")
    else:
        channel = CliChannel()
    intake = Intake(model, ledger)
    runner = Runner(model, fetcher, ledger, channel.send, trace=channel.trace, cancel=channel.cancel)
    await run(channel, intake, runner)


if __name__ == "__main__":
    asyncio.run(main())
