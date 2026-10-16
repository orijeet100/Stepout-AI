"""Web Channel (UI contract v1): the page's WebSocket and read-only JSON API, served with the built page. Listens on 127.0.0.1 only, one User.

Live frames (hello, message, trace, status) go over /ws; history is read over /api/* from `history`. Everything sent is
built from the models of contract.py, so the channel cannot drift from the contract. The channel is also the inbox: a
message sent while a Run is busy waits in `_waiting` (shown as `queued`) and is handed to the app loop one at a time.
The Web Browsing agent's page, live and view-only, is `GET /live/{run_id}` (LiveView). Security rules (docs/ui-contract.md): Host must be ours (DNS rebinding), a present Origin must be ours, a POST needs
Origin and JSON, ids are checked before any lookup, and no CORS header is ever sent. Through Tailscale Serve (`stepout remote`,
ADR 0020) the page may also be reached under exact remote host names, and only by the owner's Tailscale login.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import platform
import re
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Protocol, Sequence

from aiohttp import WSMsgType, web
from pydantic import BaseModel, TypeAdapter, ValidationError

from stepout import history
from stepout.chats import ChatKeeper
from stepout.contract import (
    Active, ClientFrame, ConversationDetail, ConversationSummary, HelloFrame, MemoryEntryOut, MessageFrame, NewConversation, Queued, RememberRequest, RenameConversation,
    SendFrame, StatusFrame, StopFrame, TraceFrame,
)
from stepout.memory_types import Memory
from stepout.domain import DEFAULT_CONVERSATION, Event, Message, Reply
from stepout.store import Store

LOCAL_USER = "local"
DIST = Path(__file__).resolve().parents[1] / "_web"  # the built page: `cd web && npm run build` writes it here, and the wheel ships it
mimetypes.add_type("application/manifest+json", ".webmanifest")  # "Add to Home Screen"
_PROXIED = ("Tailscale-User-Login", "X-Forwarded-For", "X-Forwarded-Host")  # any of these: the request came through a proxy, not straight from this laptop
HEX32 = re.compile(r"[0-9a-f]{32}")
MEMORY_ID = re.compile(r"[pfhm]-[0-9a-f]{6,12}")  # what Memory makes: p-3f9a1c, f-1a2b3c4d, h-..., m-...
MAX_TEXT = 20_000  # characters in one message (a frame is capped at 64 KB)
_CLIENT_FRAME = TypeAdapter(ClientFrame)


class HistoryReader(Protocol):
    """What the channel reads back: saved chats and runs, as the wire types of contract.py."""

    def list_conversations(self) -> list[ConversationSummary]: ...
    def get_conversation(self, conversation_id: str) -> ConversationDetail | None: ...
    def run_events(self, run_id: str) -> list[TraceFrame]: ...
    def search_conversations(self, text: str) -> list[ConversationSummary]: ...
    def export_markdown(self, conversation_id: str) -> str | None: ...


class StoreHistory:
    """The real HistoryReader: history.py over a Store."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def list_conversations(self) -> list[ConversationSummary]:
        return history.list_conversations(self._store)

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        return history.get_conversation(self._store, conversation_id)

    def run_events(self, run_id: str) -> list[TraceFrame]:
        return history.run_events(self._store, run_id)

    def search_conversations(self, text: str) -> list[ConversationSummary]:
        return history.search_conversations(self._store, text)

    def export_markdown(self, conversation_id: str) -> str | None:
        return history.export_markdown(self._store, conversation_id)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_id(value: str) -> bool:
    return value == DEFAULT_CONVERSATION or bool(HEX32.fullmatch(value))  # "default" is the CLI's chat, and any v0 page's


def _json(model: BaseModel | list[BaseModel], status: int = 200) -> web.Response:
    body = [m.model_dump(mode="json") for m in model] if isinstance(model, list) else model.model_dump(mode="json")
    return web.json_response(body, status=status)


MAX_FRAME = 1_000_000  # bytes: a 1000 by 700 JPEG is far smaller; anything bigger is not from our Browser


def _part(jpeg: bytes) -> bytes:
    return b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"


class LiveView:
    """The Assistant's headless browser, live, view-only: the newest JPEG frame of each active Run, streamed as
    multipart/x-mixed-replace (an <img src="/live/<run_id>"> shows it natively). It keeps one frame per active Run and
    nothing else: no history, no files. `is_active(run_id)` says whether a Run is running; a stream ends when it is not."""

    def __init__(self, is_active: Callable[[str], bool]) -> None:
        self._is_active = is_active
        self._frames: dict[str, bytes] = {}  # run id -> newest frame
        self._watchers: dict[str, set[asyncio.Event]] = {}  # run id -> one wake-up per open stream
        self._closed = False

    def close(self) -> None:
        """The server is stopping: finish every open stream now."""
        self._closed = True
        for run_id in list(self._watchers):
            self._wake(run_id)

    def feed(self, run_id: str, jpeg: bytes) -> None:
        """The newest frame of a Run. Synchronous and quick (the Browser calls it up to four times a second).
        Ignores anything that is not a JPEG of sane size, or is for a Run that is not active."""
        if isinstance(jpeg, bytes) and 2 < len(jpeg) <= MAX_FRAME and jpeg[:2] == b"\xff\xd8" and self._is_active(run_id):
            self._frames[run_id] = jpeg
            self._wake(run_id)

    def end(self, run_id: str) -> None:
        """The Run is over: forget its frame and let its streams finish."""
        self._frames.pop(run_id, None)
        self._wake(run_id)

    def _wake(self, run_id: str) -> None:
        for event in self._watchers.get(run_id, ()):
            event.set()

    async def stream(self, request: web.Request, run_id: str) -> web.StreamResponse:
        if not (HEX32.fullmatch(run_id) and self._is_active(run_id)):
            raise web.HTTPNotFound()
        response = web.StreamResponse(headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        await response.prepare(request)
        woken = asyncio.Event()
        self._watchers.setdefault(run_id, set()).add(woken)
        sent = None
        try:
            while not self._closed and self._is_active(run_id):
                frame = self._frames.get(run_id)
                if frame is not None and frame is not sent:  # the newest first, then each new one; a slow client skips what it missed
                    await response.write(_part(frame))
                    sent = frame
                    continue
                woken.clear()
                try:
                    await asyncio.wait_for(woken.wait(), timeout=1)
                except asyncio.TimeoutError:  # nothing new for a second: is the client still there? (a handler is not cancelled when it leaves)
                    if request.transport is None or request.transport.is_closing():
                        break
            await response.write(b"--frame--\r\n")  # the closing boundary: the Run ended
        except ConnectionError:
            pass  # the client left mid-stream
        finally:
            self._watchers[run_id].discard(woken)
            if not self._watchers[run_id]:
                del self._watchers[run_id]
        return response


class WebChannel:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, shots: Path = Path("data/runs"), *, history: HistoryReader, keeper: ChatKeeper | None = None, memory: Memory | None = None,
                 remote_hosts: Sequence[str] = (), remote_login: str = "") -> None:
        self._host, self._port, self._shots, self._history = host, port, shots, history
        self._keeper = keeper  # rename and delete (chats.py); without one the page can only read
        self._memory = memory  # what the Memory panel lists and edits; None: the panel is not offered (404)
        self._sockets: set[web.WebSocketResponse] = set()
        self._waiting: deque[Message] = deque()  # sent while a Run is busy, in order
        self._wake = asyncio.Event()
        self._busy: Message | None = None  # the message the app loop is working on
        self._run: tuple[str, str] | None = None  # (chat id, run id), known from the Run's first event
        self._cap = 0.0
        self._live = LiveView(lambda run_id: self._run is not None and self._run[1] == run_id)
        self._issued: set[str] = set()  # chat ids made by POST /api/conversations and not saved yet
        self._hosts: set[str] = set()
        self._origins: set[str] = set()
        self._remote_hosts = {h.strip().lower() for h in remote_hosts if h.strip()}  # exact names, written by `stepout remote`
        self._remote_login = remote_login.strip().lower()  # the owner's Tailscale login; without one no remote request gets in
        self._runner: web.AppRunner | None = None
        self.cancel = asyncio.Event()  # set when the User presses Stop; the Runner awaits it with every model call and hand

    # ---- the Channel interface the app loop uses -------------------------------------------------------------

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            while not self._waiting:
                self._wake.clear()
                await self._wake.wait()
            message = self._busy = self._waiting.popleft()
            self._set_run(None)
            await self._push(self._status())
            yield message
            await self._finish()  # the app loop wants the next one: this one is over, reply or not

    async def send(self, reply: Reply) -> None:
        # reply.id and reply.at are the saved copy's too (SavedChannel), so the live frame and history are one message
        await self._push(MessageFrame(id=reply.id, conversation_id=reply.conversation_id, role="assistant", text=reply.text, run_id=reply.run_id, cost_usd=reply.cost_usd, at=reply.at))
        await self._finish()

    async def trace(self, event: Event) -> None:
        """Live view of the Run: the same events the Ledger records. Never raises into the Runner."""
        if not (event.conversation_id and event.run_id):
            return
        try:
            if self._busy is not None and (self._run is None or self._run[1] != event.run_id):
                self._set_run((event.conversation_id, event.run_id))
                self._cap = self._cap_of(event.conversation_id, event.run_id)
                await self._push(self._status())
            await self._push(TraceFrame(id=event.id, conversation_id=event.conversation_id, run_id=event.run_id, parent=event.parent, kind=event.kind, role=event.role, data=event.data, cost_usd=event.cost_usd, at=event.at))
        except Exception:  # a broken page or a bad row must not stop a Run
            logging.exception("trace frame not sent")

    # ---- live state ------------------------------------------------------------------------------------------

    def _set_run(self, run: tuple[str, str] | None) -> None:
        old, self._run = self._run, run
        if old is not None and old != run:
            self._live.end(old[1])  # the Run is over: its live frame goes, and its streams finish

    def live_frame(self, run_id: str, jpeg: bytes) -> None:
        """The Browser's `on_frame`: the newest frame of a Run's page, for GET /live/{run_id}. Synchronous and quick; keeps nothing but that frame."""
        self._live.feed(run_id, jpeg)

    def _status(self) -> StatusFrame:
        active = Active(conversation_id=self._run[0], run_id=self._run[1], cap_usd=self._cap) if self._run else None
        queued = [Queued(conversation_id=m.conversation_id) for m in self._waiting]
        return StatusFrame(state="running" if self._busy else "idle", active=active, queued=queued, at=_now())

    async def _finish(self) -> None:
        if self._busy is not None:
            self._busy = None
            self._set_run(None)
            if not self._waiting:  # otherwise the next message's status follows at once
                await self._push(self._status())

    async def _push(self, frame: BaseModel) -> None:
        data = frame.model_dump(mode="json")
        for ws in list(self._sockets):
            try:
                await ws.send_json(data)
            except (ConnectionError, RuntimeError):
                self._sockets.discard(ws)

    def _cap_of(self, conversation_id: str, run_id: str) -> float:
        detail = self._history.get_conversation(conversation_id)
        return next((r.cap_usd for r in (detail.runs if detail else []) if r.run_id == run_id), 0.0)

    def _chat_state(self, conversation_id: str) -> str:
        if self._busy is not None and self._busy.conversation_id == conversation_id:
            return "running"
        return "queued" if any(m.conversation_id == conversation_id for m in self._waiting) else "idle"

    def _known(self, conversation_id: str) -> bool:
        return _valid_id(conversation_id) and (conversation_id in self._issued or conversation_id == DEFAULT_CONVERSATION or self._history.get_conversation(conversation_id) is not None)

    # ---- security: one gate in front of every route ------------------------------------------------------------

    @web.middleware
    async def _guard(self, request: web.Request, handler):
        host = (request.headers.get("Host") or "").lower()
        if host not in self._hosts:
            raise web.HTTPForbidden(text="host not allowed")  # DNS rebinding
        if host in self._remote_hosts or any(h in request.headers for h in _PROXIED):  # from another device, through Tailscale Serve
            login = request.headers.get("Tailscale-User-Login", "").strip().lower()  # set by Serve, which drops any copy the client sent
            if not self._remote_login or login != self._remote_login:
                raise web.HTTPForbidden(text="only this laptop's owner, signed in to Tailscale, may use it from another device")
        origin = request.headers.get("Origin")
        if origin is not None and origin not in self._origins:
            raise web.HTTPForbidden(text="origin not allowed")  # any page in your browser can open ws://localhost; only ours may talk to the Assistant
        if request.method in ("POST", "PATCH", "DELETE"):  # anything that changes something
            if origin is None:
                raise web.HTTPForbidden(text="origin required")
            if request.method != "DELETE" and request.content_type != "application/json":
                raise web.HTTPUnsupportedMediaType(text="application/json only")
        return await handler(request)

    # ---- HTTP ------------------------------------------------------------------------------------------------

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"app": "stepout", "v": 1})  # how `stepout` tells its own copy from something else on the port

    async def _conversations(self, request: web.Request) -> web.Response:
        query = request.query.get("q", "").strip()[:200]
        rows = {c.id: c for c in (self._history.search_conversations(query) if query else self._history.list_conversations())}
        for m in self._waiting:  # a chat whose first message is still queued is not saved yet
            if not query or query.lower() in m.text.lower():
                rows.setdefault(m.conversation_id, ConversationSummary(id=m.conversation_id, title=m.text[:60], updated_at=m.at, preview=m.text[:80], state="queued"))
        out = [c.model_copy(update={"state": self._chat_state(c.id)}) for c in rows.values()]
        return _json(sorted(out, key=lambda c: c.updated_at, reverse=True))

    async def _new_conversation(self, request: web.Request) -> web.Response:
        cid = uuid.uuid4().hex
        self._issued.add(cid)
        return _json(NewConversation(id=cid), status=201)

    async def _conversation(self, request: web.Request) -> web.Response:
        cid = request.match_info["id"]
        if not _valid_id(cid):
            raise web.HTTPNotFound()
        detail = self._history.get_conversation(cid)
        waiting = [m for m in self._waiting if m.conversation_id == cid]  # queued messages are not saved until their turn
        if detail is None and not waiting and cid not in self._issued:
            raise web.HTTPNotFound()
        detail = detail or ConversationDetail(id=cid, title=waiting[0].text[:60] if waiting else "", messages=[], runs=[])
        queued = [MessageFrame(id=m.id, conversation_id=cid, role="user", text=m.text, at=m.at) for m in waiting]
        # A Run the database still calls running is only live if it is this channel's current one: the Run after
        # the newest of this chat's while its message is busy (before its first event), or the one the events named.
        # Any other is left open by a crash.
        busy_here = self._busy is not None and self._busy.conversation_id == cid
        live = {self._run[1]} if self._run else {detail.runs[-1].run_id} if busy_here and detail.runs else set()
        runs = [r.model_copy(update={"state": "failed"}) if r.state == "running" and r.run_id not in live else r for r in detail.runs]
        return _json(detail.model_copy(update={"messages": [*detail.messages, *queued], "runs": runs}))

    async def _rename(self, request: web.Request) -> web.Response:
        cid = request.match_info["id"]
        if self._keeper is None or not _valid_id(cid):
            raise web.HTTPNotFound()
        try:
            body = RenameConversation.model_validate(await request.json())
        except (ValueError, ValidationError):
            raise web.HTTPUnprocessableEntity(text="a title of 1 to 120 characters")
        if not self._keeper.rename(cid, body.title):
            raise web.HTTPNotFound()
        return web.json_response({"id": cid, "title": body.title.strip()})

    async def _delete(self, request: web.Request) -> web.Response:
        cid = request.match_info["id"]
        if self._keeper is None or not _valid_id(cid):
            raise web.HTTPNotFound()
        if self._chat_state(cid) != "idle":
            raise web.HTTPConflict(text="this chat has a run in progress or waiting: stop it first")
        if not await self._keeper.delete(cid):
            if cid in self._issued:  # a chat that was made and never used: nothing saved, nothing to remove
                self._issued.discard(cid)
                return web.Response(status=204)
            raise web.HTTPNotFound()
        self._issued.discard(cid)
        return web.Response(status=204)

    async def _export(self, request: web.Request) -> web.Response:
        cid = request.match_info["id"]
        text = self._history.export_markdown(cid) if _valid_id(cid) else None
        if text is None:
            raise web.HTTPNotFound()
        return web.Response(text=text, content_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="chat-{cid[:8]}.md"'})

    async def _memory_list(self, request: web.Request) -> web.Response:
        if self._memory is None or not self._memory.enabled:
            raise web.HTTPNotFound()
        return _json([MemoryEntryOut(id=e.id, kind=e.kind, text=e.text, source=e.source) for e in await self._memory.entries()])

    async def _memory_add(self, request: web.Request) -> web.Response:
        if self._memory is None or not self._memory.enabled:
            raise web.HTTPNotFound()
        try:
            body = RememberRequest.model_validate(await request.json())
        except (ValueError, ValidationError):
            raise web.HTTPUnprocessableEntity(text="a line of 1 to 500 characters")
        entry = await self._memory.remember(body.text)
        return _json(MemoryEntryOut(id=entry.id, kind=entry.kind, text=entry.text, source=entry.source), status=201)

    async def _memory_edit(self, request: web.Request) -> web.Response:
        entry_id = request.match_info["id"]
        if self._memory is None or not self._memory.enabled or not MEMORY_ID.fullmatch(entry_id):
            raise web.HTTPNotFound()
        try:
            body = RememberRequest.model_validate(await request.json())
        except (ValueError, ValidationError):
            raise web.HTTPUnprocessableEntity(text="a line of 1 to 500 characters")
        entry = await self._memory.edit(entry_id, body.text)
        if entry is None:
            raise web.HTTPNotFound()
        return _json(MemoryEntryOut(id=entry.id, kind=entry.kind, text=entry.text, source=entry.source))

    async def _memory_forget(self, request: web.Request) -> web.Response:
        entry_id = request.match_info["id"]
        if self._memory is None or not self._memory.enabled or not MEMORY_ID.fullmatch(entry_id):
            raise web.HTTPNotFound()
        if await self._memory.forget(entry_id) is None:
            raise web.HTTPNotFound()
        return web.Response(status=204)

    async def _run_events(self, request: web.Request) -> web.Response:
        run = request.match_info["run"]
        events = self._history.run_events(run) if HEX32.fullmatch(run) else []
        if not events:
            raise web.HTTPNotFound()
        return _json(events)

    async def _shot(self, request: web.Request) -> web.StreamResponse:
        run, name = request.match_info["run"], request.match_info["name"]
        path = self._shots / run / name
        if not (HEX32.fullmatch(run) and re.fullmatch(r"\d+\.jpg", name) and path.is_file()):
            raise web.HTTPNotFound()  # only files this Assistant wrote: no traversal, no guessing
        return web.FileResponse(path)

    async def _live_stream(self, request: web.Request) -> web.StreamResponse:
        return await self._live.stream(request, request.match_info["run"])

    async def _index(self, request: web.Request) -> web.StreamResponse:
        index = DIST / "index.html"
        if not index.exists():
            return web.Response(status=503, text="Web page not built. Run: cd web && npm install && npm run build")  # a source checkout only: the wheel ships it
        return web.FileResponse(index)

    # ---- WebSocket -------------------------------------------------------------------------------------------

    async def _ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024)
        await ws.prepare(request)
        self._sockets.add(ws)
        try:
            await ws.send_json(HelloFrame(machine=platform.node()).model_dump(mode="json"))
            await ws.send_json(self._status().model_dump(mode="json"))
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._on_text(msg.data)
        finally:
            self._sockets.discard(ws)
        return ws

    async def _on_text(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except ValueError:
            return
        if isinstance(data, dict) and "type" not in data:  # a v0 page (accepted for one release): {"text": ...} or {"stop": true}
            data = {"type": "stop"} if data.get("stop") else {"type": "send", "conversation_id": DEFAULT_CONVERSATION, "text": data.get("text")}
        try:
            frame = _CLIENT_FRAME.validate_python(data)
        except ValidationError:
            return
        if isinstance(frame, StopFrame):
            self.cancel.set()
            return
        assert isinstance(frame, SendFrame)
        text = frame.text.strip()
        if not text or len(text) > MAX_TEXT or not self._known(frame.conversation_id):
            return
        message = Message(user_id=LOCAL_USER, text=text, conversation_id=frame.conversation_id)
        await self._push(MessageFrame(id=message.id, conversation_id=message.conversation_id, role="user", text=text, at=message.at))
        self._waiting.append(message)
        self._wake.set()
        if self._busy is not None:
            await self._push(self._status())  # show `queued` right away; an idle channel picks the message up at once

    # ---- lifecycle -------------------------------------------------------------------------------------------

    async def start(self) -> int:
        """Start serving; returns the bound port (pass port=0 to pick a free one)."""
        app = web.Application(middlewares=[self._guard])
        app.add_routes(
            [
                web.get("/", self._index),
                web.get("/ws", self._ws),
                web.get("/api/health", self._health),
                web.get("/api/conversations", self._conversations),
                web.post("/api/conversations", self._new_conversation),
                web.get("/api/conversations/{id}", self._conversation),
                web.patch("/api/conversations/{id}", self._rename),
                web.delete("/api/conversations/{id}", self._delete),
                web.get("/api/conversations/{id}/export", self._export),
                web.get("/api/memory", self._memory_list),
                web.post("/api/memory", self._memory_add),
                web.patch("/api/memory/{id}", self._memory_edit),
                web.delete("/api/memory/{id}", self._memory_forget),
                web.get("/api/runs/{run}/events", self._run_events),
                web.get("/shots/{run}/{name}", self._shot),
                web.get("/live/{run}", self._live_stream),
            ]
        )
        if DIST.is_dir():
            app.router.add_static("/", DIST)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self._host, self._port).start()
        self._port = self._runner.addresses[0][1]
        local = {f"127.0.0.1:{self._port}", f"localhost:{self._port}"}
        self._hosts = local | self._remote_hosts
        self._origins = {f"http://{h}" for h in local} | {f"https://{h}" for h in self._remote_hosts}
        return self._port

    async def stop(self) -> None:
        self._live.close()  # open live streams end now: shutting down must not wait for a Run
        for ws in list(self._sockets):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()
