"""Mock backend for the page: speaks the v1 contract (docs/ui-contract.md) from web/fixtures/, with no model and no cost.

    python web/mock/server.py [--port 8766] [--speed 1]      then:  cd web && npm run dev

History (GET /api/...) is built from the fixtures. A `send` over /ws picks a recorded run by keyword, then replays its
events with the recorded gaps (times scaled by --speed, each gap capped at 4 s), under fresh ids, as the real server
would stream them. `stop` ends the replay at the next event. One run at a time; messages sent meanwhile are queued.
The security rules are the real channel's (Host check, Origin and JSON content type on POST, 32-hex ids, no CORS), so
the dev proxy is tested against them. Replays live in memory only: restart the mock and they are gone.

Live view: `GET /live/{run_id}` runs the channel's own `LiveView` (so the page is built against the real streaming
code). While a replayed Run has a Browser step it feeds that view about four frames a second: a blank page at first, then
the fixture screenshot of the page the Browser has "opened" (the `shot` events' images), as the real Browser will.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import WSMsgType, web

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from stepout.channels.web import LiveView  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FRAME_EVERY = 0.25  # seconds: the real Browser sends at most four a second
HEX32 = re.compile(r"[0-9a-f]{32}")
WORKER = web.AppKey("worker", asyncio.Task)
MAX_GAP = 4.0  # seconds, before --speed
MAX_TEXT = 20_000
CAP = 1.0

# first keyword hit wins; no hit means the Luma web run
ROUTES = [
    ("declined", re.compile(r"\b(pay|invoice|transfer|delete|password)\b", re.I)),
    ("files-run", re.compile(r"\b(pdfs?|folders?|files?)\b", re.I)),
    ("refused-action", re.compile(r"\b(weather|forecast)\b", re.I)),
    ("stopped", re.compile(r"\b(blog|summari[sz]e)\b", re.I)),
    ("over-budget", re.compile(r"\b(compare|every|all the)\b", re.I)),
    ("chat-reply", re.compile(r"\d\s*[-+*/]\s*\d")),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def secs(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


class Mock:
    def __init__(self, speed: float = 1.0) -> None:
        self.speed = speed
        self.chats: dict[str, dict] = {}  # id -> {"messages": [...], "events": [...]}
        self.scenarios: dict[str, list[dict]] = {}  # name -> frames to replay (no user message, no status)
        self.sockets: set[web.WebSocketResponse] = set()
        self.pending: list[tuple[str, str]] = []  # (conversation id, text) waiting for the active run
        self.active: dict | None = None  # {"conversation_id", "run_id", "cancel": asyncio.Event}
        self.wake = asyncio.Event()
        self.live = LiveView(lambda run_id: self.active is not None and self.active["run_id"] == run_id)
        self.page = b""  # the frame the replayed Browser is showing now
        for path in sorted(FIXTURES.glob("*.json")):
            frames = json.loads(path.read_text(encoding="utf-8"))
            chat = self.chats.setdefault(frames[0]["conversation_id"], {"messages": [], "events": []})
            chat["messages"] += [f for f in frames if f["type"] == "message"]
            chat["events"] += [f for f in frames if f["type"] == "trace"]
            self.scenarios[path.stem] = [f for f in frames if f["type"] != "status" and not (f["type"] == "message" and f["role"] == "user")]

    # ---- frames out ------------------------------------------------------------------------------------------

    def status(self) -> dict:
        active = {k: self.active[k] for k in ("conversation_id", "run_id")} | {"cap_usd": CAP} if self.active else None
        return {
            "type": "status",
            "state": "running" if self.active else "idle",
            "active": active,
            "queued": [{"conversation_id": c} for c, _ in self.pending],
            "at": now(),
        }

    async def broadcast(self, frame: dict) -> None:
        for ws in list(self.sockets):
            try:
                await ws.send_json(frame)
            except ConnectionError:
                self.sockets.discard(ws)

    async def emit(self, conv: str, frame: dict) -> None:
        chat = self.chats[conv]
        chat["messages" if frame["type"] == "message" else "events"].append(frame)
        await self.broadcast(frame)

    # ---- the run worker --------------------------------------------------------------------------------------

    async def worker(self) -> None:
        while True:
            await self.wake.wait()
            self.wake.clear()
            while self.pending:
                conv, text = self.pending.pop(0)
                await self.replay(conv, text)
            await self.broadcast(self.status())

    async def replay(self, conv: str, text: str) -> None:
        name = next((n for n, rx in ROUTES if rx.search(text)), "web-run")
        frames = self.scenarios[name]
        if not any(f["type"] == "trace" for f in frames):  # a decline: just the reply
            await self.sleep(1.0)
            await self.emit(conv, {**frames[0], "id": uuid.uuid4().hex, "conversation_id": conv, "at": now()})
            return
        run = uuid.uuid4().hex
        cancel = asyncio.Event()
        self.active = {"conversation_id": conv, "run_id": run, "cancel": cancel}
        await self.broadcast(self.status())
        await self.sleep(1.0)  # the first model call: like the real backend, the Run exists (and is listed) a moment before its first event
        ids: dict[str, str] = {}
        spent, last = 0.0, frames[0]["at"]
        pump: asyncio.Task | None = None
        try:
            for f in frames:
                if await self.sleep(min(secs(last, f["at"]), MAX_GAP), cancel):
                    role = "orchestrator"
                    await self.emit(conv, self.trace(conv, run, None, "stop", role, {"summary": "Stopped by you."}, 0.0))
                    await self.emit(conv, self.message(conv, "assistant", "Stopped by you.", run, spent))
                    break
                last = f["at"]
                ids[f["id"]] = uuid.uuid4().hex
                if f["type"] == "trace":
                    spent += f["cost_usd"]
                    await self.emit(conv, {**f, "id": ids[f["id"]], "conversation_id": conv, "run_id": run, "parent": ids.get(f["parent"]), "at": now()})
                    if f["kind"] == "step" and f["data"].get("action", {}).get("kind") == "browse" and pump is None:
                        self.page = (FIXTURES / "blank.jpg").read_bytes()  # the Browser has opened a page: it has not painted yet
                        pump = asyncio.create_task(self.pump(run))
                    if f["kind"] == "shot":
                        self.page = (FIXTURES / "shots" / f["data"]["shot"]).read_bytes()  # ... and now it has
                else:
                    await self.emit(conv, {**f, "id": ids[f["id"]], "conversation_id": conv, "run_id": run, "cost_usd": round(spent, 4), "at": now()})
        finally:
            if pump:
                pump.cancel()
            self.active = None
            self.live.end(run)  # the Run is over: its streams finish

    async def pump(self, run: str) -> None:
        """The Browser's on_frame, replayed: the current page, about four times a second, while the Run runs."""
        while True:
            self.live.feed(run, self.page)
            await asyncio.sleep(FRAME_EVERY)

    async def sleep(self, seconds: float, cancel: asyncio.Event | None = None) -> bool:
        """Wait (scaled by --speed); True if Stop was pressed meanwhile."""
        try:
            if cancel is None:
                await asyncio.sleep(seconds * self.speed)
                return False
            await asyncio.wait_for(cancel.wait(), seconds * self.speed)
            return True
        except asyncio.TimeoutError:
            return False

    def message(self, conv: str, role: str, text: str, run: str | None = None, cost: float | None = None) -> dict:
        return {"type": "message", "id": uuid.uuid4().hex, "conversation_id": conv, "role": role, "text": text, "run_id": run, "cost_usd": cost, "at": now()}

    def trace(self, conv: str, run: str, parent: str | None, kind: str, role: str, data: dict, cost: float) -> dict:
        return {"type": "trace", "id": uuid.uuid4().hex, "conversation_id": conv, "run_id": run, "parent": parent, "kind": kind, "role": role, "data": data, "cost_usd": cost, "at": now()}

    # ---- security: the same rules as the real channel --------------------------------------------------------

    @web.middleware
    async def guard(self, request: web.Request, handler):
        port = request.transport.get_extra_info("sockname")[1]
        if request.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            raise web.HTTPForbidden(text="host not allowed")  # DNS rebinding
        if request.method == "POST":
            if request.content_type != "application/json":
                raise web.HTTPUnsupportedMediaType(text="application/json only")
            if request.headers.get("Origin") not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                raise web.HTTPForbidden(text="origin not allowed")
        return await handler(request)

    # ---- HTTP ------------------------------------------------------------------------------------------------

    def chat_or_404(self, request: web.Request) -> tuple[str, dict]:
        cid = request.match_info["id"]
        if not HEX32.fullmatch(cid) or cid not in self.chats:
            raise web.HTTPNotFound()
        return cid, self.chats[cid]

    def title(self, chat: dict) -> str:
        first = next((m for m in chat["messages"] if m["role"] == "user"), None)
        return cut(first["text"], 60) if first else ""

    def chat_state(self, cid: str) -> str:
        if self.active and self.active["conversation_id"] == cid:
            return "running"
        return "queued" if any(c == cid for c, _ in self.pending) else "idle"

    async def conversations(self, request: web.Request) -> web.Response:
        rows = []
        for cid, chat in self.chats.items():
            last = max([*chat["messages"], *chat["events"]], key=lambda f: f["at"], default=None)
            msgs = chat["messages"]
            rows.append({"id": cid, "title": self.title(chat), "updated_at": last["at"] if last else now(), "preview": cut(msgs[-1]["text"], 80) if msgs else "", "state": self.chat_state(cid)})
        return web.json_response(sorted(rows, key=lambda r: r["updated_at"], reverse=True))

    async def new_conversation(self, request: web.Request) -> web.Response:
        cid = uuid.uuid4().hex
        self.chats[cid] = {"messages": [], "events": []}
        return web.json_response({"id": cid}, status=201)

    async def conversation(self, request: web.Request) -> web.Response:
        cid, chat = self.chat_or_404(request)
        runs = []
        for run_id in dict.fromkeys(e["run_id"] for e in chat["events"]):
            events = [e for e in chat["events"] if e["run_id"] == run_id]
            before = [m for m in chat["messages"] if m["role"] == "user" and m["at"] <= events[0]["at"]]
            state = "running" if self.active and self.active["run_id"] == run_id else "stopped" if any(e["kind"] == "stop" for e in events) else "done"
            runs.append(
                {
                    "run_id": run_id,
                    "request": before[-1]["text"] if before else "",
                    "state": state,
                    "cost_usd": round(sum(e["cost_usd"] for e in events), 4),
                    "cap_usd": CAP,
                    "steps": sum(e["kind"] == "step" for e in events),
                    "started_at": events[0]["at"],
                    "ended_at": None if state == "running" else events[-1]["at"],
                }
            )
        if self.active and self.active["conversation_id"] == cid and not any(r["run_id"] == self.active["run_id"] for r in runs):
            asked = [m for m in chat["messages"] if m["role"] == "user"]  # a Run that has just started: listed, with no events yet (history.py does the same)
            runs.append({"run_id": self.active["run_id"], "request": asked[-1]["text"] if asked else "", "state": "running", "cost_usd": 0.0, "cap_usd": CAP, "steps": 0, "started_at": now(), "ended_at": None})
        return web.json_response({"id": cid, "title": self.title(chat), "messages": chat["messages"], "runs": runs})

    async def run_events(self, request: web.Request) -> web.Response:
        run_id = request.match_info["run"]
        events = [e for c in self.chats.values() for e in c["events"] if e["run_id"] == run_id] if HEX32.fullmatch(run_id) else []
        if not events:
            raise web.HTTPNotFound()
        return web.json_response(events)

    async def shot(self, request: web.Request) -> web.StreamResponse:
        run, name = request.match_info["run"], request.match_info["name"]
        path = FIXTURES / "shots" / run / name
        if not (HEX32.fullmatch(run) and re.fullmatch(r"\d+\.jpg", name) and path.is_file()):
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def live_stream(self, request: web.Request) -> web.StreamResponse:
        return await self.live.stream(request, request.match_info["run"])

    # ---- WebSocket -------------------------------------------------------------------------------------------

    async def ws(self, request: web.Request) -> web.WebSocketResponse:
        port = request.transport.get_extra_info("sockname")[1]
        origin = request.headers.get("Origin")
        if origin is not None and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            raise web.HTTPForbidden(text="origin not allowed")
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024)
        await ws.prepare(request)
        self.sockets.add(ws)
        await ws.send_json({"type": "hello", "v": 1})
        await ws.send_json(self.status())
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self.on_frame(msg.data)
        finally:
            self.sockets.discard(ws)
        return ws

    async def on_frame(self, raw: str) -> None:
        try:
            frame = json.loads(raw)
            kind = frame["type"]
        except (ValueError, KeyError, TypeError):
            return
        if kind == "stop" and self.active:
            self.active["cancel"].set()
        elif kind == "send":
            conv, text = frame.get("conversation_id"), frame.get("text")
            if not (isinstance(conv, str) and HEX32.fullmatch(conv) and conv in self.chats and isinstance(text, str)):
                return
            text = text.strip()
            if not text or len(text) > MAX_TEXT:
                return
            await self.emit(conv, self.message(conv, "user", text))
            self.pending.append((conv, text))
            await self.broadcast(self.status())  # shows `queued` right away if a run is busy
            self.wake.set()


def make_app(speed: float = 1.0) -> web.Application:
    mock = Mock(speed)
    app = web.Application(middlewares=[mock.guard])
    app.add_routes(
        [
            web.get("/api/conversations", mock.conversations),
            web.post("/api/conversations", mock.new_conversation),
            web.get("/api/conversations/{id}", mock.conversation),
            web.get("/api/runs/{run}/events", mock.run_events),
            web.get("/shots/{run}/{name}", mock.shot),
            web.get("/live/{run}", mock.live_stream),
            web.get("/ws", mock.ws),
        ]
    )

    async def start_worker(app: web.Application) -> None:
        app[WORKER] = asyncio.create_task(mock.worker())

    async def stop_worker(app: web.Application) -> None:
        app[WORKER].cancel()

    app.on_startup.append(start_worker)
    app.on_cleanup.append(stop_worker)
    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--speed", type=float, default=1.0, help="multiplier on the recorded gaps (0.2 = five times faster)")
    args = ap.parse_args()
    web.run_app(make_app(args.speed), host="127.0.0.1", port=args.port)
