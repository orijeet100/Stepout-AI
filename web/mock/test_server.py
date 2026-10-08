"""Checks for the mock and its fixtures.  Run:  python -m pytest web/mock -q   (the Main lane's pytest only collects tests/)."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import aiohttp
import pytest
from aiohttp import WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).parent))
from server import FIXTURES, make_app  # noqa: E402

HEX32 = re.compile(r"[0-9a-f]{32}")
ISO_Z = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z")


def drive(speed, scenario):
    """Run `scenario(client)` against a fresh mock; speed 0 replays instantly."""

    async def go():
        async with TestClient(TestServer(make_app(speed))) as client:
            return await scenario(client)

    return asyncio.run(go())


def origin(c: TestClient) -> dict:
    return {"Origin": f"http://127.0.0.1:{c.port}"}


async def frames_until(ws, done, timeout=10):
    seen: list[dict] = []
    async with asyncio.timeout(timeout):
        while not done(seen):
            seen.append(json.loads((await ws.receive()).data))
    return seen


async def new_chat(c: TestClient) -> str:
    r = await c.post("/api/conversations", json={}, headers=origin(c))
    assert r.status == 201
    return (await r.json())["id"]


# ---- the fixtures are valid v1 frames ---------------------------------------------------------------------------


def test_every_fixture_is_a_list_of_valid_v1_frames():
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 7
    for path in files:
        frames = json.loads(path.read_text(encoding="utf-8"))
        seen: set[str] = set()
        convs = {f["conversation_id"] for f in frames if "conversation_id" in f}
        assert len(convs) == 1 and all(HEX32.fullmatch(c) for c in convs), path.name
        assert [f["at"] for f in frames] == sorted(f["at"] for f in frames), f"{path.name}: times go backwards"
        for f in frames:
            assert ISO_Z.fullmatch(f["at"]), (path.name, f["at"])
            if f["type"] == "status":
                assert f["state"] in ("idle", "running") and isinstance(f["queued"], list)
                assert f["active"] is None or {"conversation_id", "run_id", "cap_usd"} <= f["active"].keys()
                continue
            assert HEX32.fullmatch(f["id"]) and f["id"] not in seen
            seen.add(f["id"])
            if f["type"] == "message":
                assert f["role"] in ("user", "assistant")
                assert f["run_id"] is None or HEX32.fullmatch(f["run_id"])
                assert f["cost_usd"] is None or isinstance(f["cost_usd"], float)
                assert "(cost:" not in f["text"]  # v1 has cost_usd; no footer
                if f["role"] == "user":
                    assert f["run_id"] is None and f["cost_usd"] is None
            else:
                assert f["type"] == "trace" and HEX32.fullmatch(f["run_id"]) and isinstance(f["cost_usd"], float)
                assert f["parent"] is None or f["parent"] in seen, f"{path.name}: parent comes after its child"
                assert isinstance(f["data"], dict)
                if f["kind"] == "shot":
                    assert (FIXTURES / "shots" / f["data"]["shot"]).is_file() and f["data"]["url"] and f["data"]["title"]
        # the reply's cost is the sum of the run's events
        replies = [f for f in frames if f["type"] == "message" and f["role"] == "assistant" and f["run_id"]]
        for r in replies:
            total = sum(f["cost_usd"] for f in frames if f["type"] == "trace" and f["run_id"] == r["run_id"])
            assert r["cost_usd"] == pytest.approx(total, abs=1e-4), path.name


def test_fixtures_cover_every_case_the_plan_lists():
    kinds = {k for p in FIXTURES.glob("*.json") for f in json.loads(p.read_text(encoding="utf-8")) if f["type"] == "trace" for k in (f["kind"], f["data"].get("verdict"))}
    assert {"plan", "step", "return", "shot", "stop", "refuse", "allow"} <= kinds
    assert not any("D:\\" in p.read_text(encoding="utf-8") and "Example" not in p.read_text(encoding="utf-8") for p in FIXTURES.glob("*.json"))  # invented paths only


# ---- HTTP -------------------------------------------------------------------------------------------------------


def test_history_comes_from_the_fixtures_newest_first():
    async def scenario(c):
        chats = await (await c.get("/api/conversations")).json()
        assert len(chats) == 7 and chats[0]["title"].startswith("What are the top three events")
        assert all(x["state"] == "idle" for x in chats)
        assert [x["updated_at"] for x in chats] == sorted((x["updated_at"] for x in chats), reverse=True)

        detail = await (await c.get(f"/api/conversations/{chats[0]['id']}")).json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        run = detail["runs"][0]
        assert run["state"] == "done" and run["cap_usd"] == 1.0 and run["steps"] > 0 and run["request"] == detail["messages"][0]["text"]

        events = await (await c.get(f"/api/runs/{run['run_id']}/events")).json()
        assert events[0]["kind"] == "step" and any(e["kind"] == "shot" for e in events)
        shot = next(e for e in events if e["kind"] == "shot")["data"]["shot"]
        r = await c.get(f"/shots/{shot}")
        assert r.status == 200 and r.content_type == "image/jpeg"

        over = next(x for x in chats if x["title"].startswith("Compare"))
        runs = (await (await c.get(f"/api/conversations/{over['id']}")).json())["runs"]
        assert runs[0]["state"] == "stopped" and runs[0]["cost_usd"] >= runs[0]["cap_usd"]

    drive(0, scenario)


def test_ids_are_validated_before_any_lookup():
    async def scenario(c):
        for path in ["/api/conversations/nope", "/api/conversations/" + "0" * 32, "/api/runs/..%2f..%2fsecret/events", "/shots/zzzz/1.jpg",
                     "/shots/" + "0" * 32 + "/1.jpg", "/shots/..%2f/1.jpg"]:
            assert (await c.get(path)).status == 404, path

    drive(0, scenario)


def test_host_origin_and_content_type_rules():
    async def scenario(c):
        assert (await c.get("/api/conversations", headers={"Host": "evil.example"})).status == 403  # DNS rebinding
        assert (await c.get("/api/conversations", headers={"Host": f"evil.example:{c.port}"})).status == 403
        assert (await c.get("/api/conversations", headers={"Host": f"localhost:{c.port}"})).status == 200
        assert (await c.post("/api/conversations", data="{}", headers=origin(c))).status == 415  # not JSON
        assert (await c.post("/api/conversations", json={}, headers={"Origin": "http://evil.example"})).status == 403
        assert (await c.post("/api/conversations", json={})).status == 403  # no Origin on a POST
        r = await c.post("/api/conversations", json={}, headers=origin(c))
        assert r.status == 201 and HEX32.fullmatch((await r.json())["id"])
        with pytest.raises(WSServerHandshakeError) as err:
            await c.ws_connect("/ws", headers={"Origin": "http://evil.example"})
        assert err.value.status == 403
        for r in [await c.get("/api/conversations"), await c.post("/api/conversations", json={}, headers=origin(c))]:
            assert not [h for h in r.headers if h.lower().startswith("access-control-")]  # never any CORS headers

    drive(0, scenario)


# ---- WebSocket --------------------------------------------------------------------------------------------------


def test_send_replays_a_run_under_fresh_ids():
    async def scenario(c):
        cid = await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        first = await frames_until(ws, lambda s: len(s) == 2)
        assert first[0] == {"type": "hello", "v": 1} and first[1]["state"] == "idle" and first[1]["queued"] == []

        await ws.send_json({"type": "send", "conversation_id": cid, "text": "What is 2 + 3?"})
        got = await frames_until(ws, lambda s: bool(s) and s[-1]["type"] == "status" and s[-1]["state"] == "idle" and any(f["type"] == "message" and f["role"] == "assistant" for f in s))
        assert got[0]["type"] == "message" and got[0]["role"] == "user" and got[0]["text"] == "What is 2 + 3?" and got[0]["run_id"] is None
        running = next(f for f in got if f["type"] == "status" and f["state"] == "running")
        run = running["active"]["run_id"]
        assert running["active"]["conversation_id"] == cid and running["active"]["cap_usd"] == 1.0
        traces = [f for f in got if f["type"] == "trace"]
        reply = got[-2]
        assert traces and all(t["run_id"] == run and t["conversation_id"] == cid and ISO_Z.fullmatch(t["at"]) for t in traces)
        assert reply["role"] == "assistant" and reply["run_id"] == run and reply["cost_usd"] == pytest.approx(sum(t["cost_usd"] for t in traces), abs=1e-4)

        detail = await (await c.get(f"/api/conversations/{cid}")).json()  # history sees what was streamed
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] and detail["runs"][0]["run_id"] == run and detail["title"] == "What is 2 + 3?"
        await ws.close()

    drive(0, scenario)


def test_bad_send_frames_are_ignored():
    async def scenario(c):
        cid = await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        await frames_until(ws, lambda s: len(s) == 2)
        for bad in [{"type": "send", "conversation_id": "x", "text": "hi"}, {"type": "send", "conversation_id": "0" * 32, "text": "hi"},
                    {"type": "send", "conversation_id": cid, "text": "   "}, {"type": "send", "conversation_id": cid, "text": 5},
                    {"type": "send", "conversation_id": cid, "text": "x" * 20_001}, {"type": "nonsense"}, {"no": "type"}, [1]]:
            await ws.send_json(bad)
        await ws.send_str("not json")
        await ws.send_json({"type": "send", "conversation_id": cid, "text": "ok"})
        first = await frames_until(ws, lambda s: len(s) == 1)
        assert first[0]["type"] == "message" and first[0]["text"] == "ok"  # nothing before it: the bad ones did nothing
        await ws.close()

    drive(0, scenario)


def test_stop_ends_the_run_at_the_next_event():
    async def scenario(c):
        cid = await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        await frames_until(ws, lambda s: len(s) == 2)
        await ws.send_json({"type": "send", "conversation_id": cid, "text": "events this weekend"})  # the long web run
        await frames_until(ws, lambda s: any(f["type"] == "trace" for f in s))
        await ws.send_json({"type": "stop"})
        rest = await frames_until(ws, lambda s: any(f["type"] == "message" and f["role"] == "assistant" for f in s))
        stop = next(f for f in rest if f["type"] == "trace" and f["kind"] == "stop")
        assert stop["data"]["summary"] == "Stopped by you."
        assert next(f for f in rest if f["type"] == "message")["text"] == "Stopped by you."
        idle = await frames_until(ws, lambda s: bool(s) and s[-1]["type"] == "status")
        assert idle[-1]["state"] == "idle"
        runs = (await (await c.get(f"/api/conversations/{cid}")).json())["runs"]
        assert runs[0]["state"] == "stopped"
        await ws.close()

    drive(0.02, scenario)


def test_a_message_sent_during_a_run_is_queued():
    async def scenario(c):
        a, b = await new_chat(c), await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        await frames_until(ws, lambda s: len(s) == 2)
        await ws.send_json({"type": "send", "conversation_id": a, "text": "events this weekend"})
        await ws.send_json({"type": "send", "conversation_id": b, "text": "What is 2 + 3?"})
        got = await frames_until(ws, lambda s: sum(f["type"] == "message" and f["role"] == "assistant" for f in s) == 2, timeout=20)
        statuses = [f for f in got if f["type"] == "status"]
        assert any(s["queued"] == [{"conversation_id": b}] for s in statuses)  # b waited behind a
        replies = [f["conversation_id"] for f in got if f["type"] == "message" and f["role"] == "assistant"]
        assert replies == [a, b]
        assert got[-1]["type"] in ("message", "status")
        await ws.close()

    drive(0.02, scenario)


# ---- the live view -----------------------------------------------------------------------------------------------


def test_a_replayed_browser_run_streams_live_frames_and_the_stream_ends_with_the_run():
    pages = {p.read_bytes() for p in (FIXTURES / "shots").glob("*/*.jpg")} | {(FIXTURES / "blank.jpg").read_bytes()}

    async def scenario(c):
        cid = await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        await frames_until(ws, lambda s: len(s) == 2)
        await ws.send_json({"type": "send", "conversation_id": cid, "text": "events this weekend"})
        got = await frames_until(ws, lambda s: any(f["type"] == "trace" and f["kind"] == "step" and f["data"].get("action", {}).get("kind") == "browse" for f in s))
        run = next(f for f in got if f["type"] == "status" and f["active"])["active"]["run_id"]

        assert (await c.get("/live/" + "0" * 32)).status == 404  # no such Run
        assert (await c.get("/live/not-an-id")).status == 404
        assert (await c.get(f"/live/{run}", headers={"Host": "evil.example"})).status == 403  # the same guard as every route

        resp = await c.get(f"/live/{run}")
        assert resp.status == 200 and resp.headers["Content-Type"].startswith("multipart/x-mixed-replace")
        reader = aiohttp.MultipartReader.from_response(resp)
        seen = []
        async with asyncio.timeout(20):
            while (part := await reader.next()) is not None:  # ends by itself when the replayed Run ends
                seen.append(bytes(await part.read()))
        assert len(seen) >= 2 and all(f[:2] == b"\xff\xd8" for f in seen)  # JPEGs, one after another
        assert all(f in pages for f in seen)  # the blank page and the fixture screenshots, nothing invented
        assert any(f != seen[0] for f in seen)  # the page changed while we watched (blank, then a screenshot)

        assert (await c.get(f"/live/{run}")).status == 404  # the Run is over
        await ws.close()

    drive(0.1, scenario)


def test_a_run_without_a_browser_step_has_nothing_to_stream_until_it_ends():
    async def scenario(c):
        cid = await new_chat(c)
        ws = await c.ws_connect("/ws", headers=origin(c))
        await frames_until(ws, lambda s: len(s) == 2)
        await ws.send_json({"type": "send", "conversation_id": cid, "text": "What is 2 + 3?"})
        got = await frames_until(ws, lambda s: any(f["type"] == "status" and f["active"] for f in s))
        run = next(f for f in got if f["type"] == "status" and f["active"])["active"]["run_id"]
        resp = await c.get(f"/live/{run}")
        reader = aiohttp.MultipartReader.from_response(resp)
        async with asyncio.timeout(10):
            assert await reader.next() is None  # no Browser step, so no frame: the stream just ends with the Run
        await ws.close()

    drive(0.05, scenario)
