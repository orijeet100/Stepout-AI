"""Web Channel: a WebSocket chat page, served from web/dist. Localhost only, one User."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from aiohttp import WSMsgType, web

from stepout.domain import Event, Message, Reply

LOCAL_USER = "local"
DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class WebChannel:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._host, self._port = host, port
        self._inbox: asyncio.Queue[Message] = asyncio.Queue()
        self._sockets: set[web.WebSocketResponse] = set()
        self._history: list[dict] = []  # replayed on connect, so a refresh keeps the chat (in memory only)
        self._origins: set[str] = set()
        self._runner: web.AppRunner | None = None
        self.cancel = asyncio.Event()  # set when the User presses Stop; the Runner checks it between steps

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            yield await self._inbox.get()

    async def send(self, reply: Reply) -> None:
        await self._push({"role": "assistant", "text": reply.text})

    async def trace(self, event: Event) -> None:
        """Live view of the Run: the same events the Ledger records."""
        await self._push({"type": "trace", **event.model_dump(mode="json", include={"kind", "role", "data", "cost_usd"})})

    async def _push(self, item: dict) -> None:
        self._history.append(item)
        for ws in list(self._sockets):
            try:
                await ws.send_json(item)
            except ConnectionError:
                self._sockets.discard(ws)

    async def _ws(self, request: web.Request) -> web.WebSocketResponse:
        # Any page in your browser can open ws://localhost; only our own page may talk to the Assistant.
        origin = request.headers.get("Origin")
        if origin is not None and origin not in self._origins:
            raise web.HTTPForbidden(text="origin not allowed")

        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024)
        await ws.prepare(request)
        self._sockets.add(ws)
        for item in self._history:
            await ws.send_json(item)
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(msg.data)
                    stop, text = bool(data.get("stop")), str(data.get("text", "")).strip()
                except (ValueError, AttributeError):
                    continue
                if stop:
                    self.cancel.set()
                elif text:
                    await self._push({"role": "user", "text": text})
                    self._inbox.put_nowait(Message(user_id=LOCAL_USER, text=text))
        finally:
            self._sockets.discard(ws)
        return ws

    async def _index(self, request: web.Request) -> web.StreamResponse:
        index = DIST / "index.html"
        if not index.exists():
            return web.Response(status=503, text="Web page not built. Run: cd web && npm install && npm run build")
        return web.FileResponse(index)

    async def start(self) -> int:
        """Start serving; returns the bound port (pass port=0 to pick a free one)."""
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._ws)
        if DIST.is_dir():
            app.router.add_static("/", DIST)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self._host, self._port).start()
        self._port = self._runner.addresses[0][1]
        self._origins = {f"http://127.0.0.1:{self._port}", f"http://localhost:{self._port}"}
        return self._port

    async def stop(self) -> None:
        for ws in list(self._sockets):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()
