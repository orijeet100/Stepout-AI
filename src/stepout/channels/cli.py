"""CLI Channel: stdin in, stdout out. The allowlisted User is the local terminal user."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from stepout.domain import Event, Message, Reply

LOCAL_USER = "local"


class CliChannel:
    def __init__(self) -> None:
        self.cancel = asyncio.Event()  # never set: the terminal is busy while a Run works

    async def messages(self) -> AsyncIterator[Message]:
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, "> ")
            except EOFError:
                return
            if line.strip():
                yield Message(user_id=LOCAL_USER, text=line)

    async def send(self, reply: Reply) -> None:
        print(reply.text)

    async def trace(self, event: Event) -> None:
        if event.kind != "plan":  # plan snapshots are for the web checklist; the step lines say the same
            print(f"  · {event.role}: {event.data['summary']}")
