"""CLI Channel: stdin in, stdout out. The allowlisted User is the local terminal user."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from stepout.domain import Message, Reply

LOCAL_USER = "local"


class CliChannel:
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
