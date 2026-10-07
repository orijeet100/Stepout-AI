"""Composition root: wiring, the receive -> read -> submit loop."""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from stepout.channels.cli import CliChannel
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
        reading = await intake.read(message)
        match reading:
            case DeclinedReading(reason=reason, alternative=alternative):
                await channel.send(Reply(text=f"{reason} {alternative}"))
            case CommandReading(name=name):
                await channel.send(Reply(text=f"Unknown command: /{name}"))
            case NewTask(request=request, route=route):
                task = Task(user_id=message.user_id, request=request, route=route)
                await runner.submit(task)


async def main() -> None:
    load_dotenv()
    store = Store(DB_PATH)
    ledger = Ledger(store)
    model = AnthropicModel()
    fetcher = Fetcher()
    channel = CliChannel()
    intake = Intake(model, ledger)
    runner = Runner(model, fetcher, ledger, channel.send)
    await run(channel, intake, runner)


if __name__ == "__main__":
    asyncio.run(main())
