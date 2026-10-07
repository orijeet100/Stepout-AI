import asyncio

import aiohttp
import pytest

from stepout.channels.web import WebChannel
from stepout.domain import Event, Reply


@pytest.fixture
async def served():
    channel = WebChannel(port=0)
    port = await channel.start()
    yield channel, f"http://127.0.0.1:{port}"
    await channel.stop()


async def test_message_in_and_reply_out(served):
    channel, base = served
    async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws", origin=base) as ws:
        await ws.send_json({"text": "hello"})
        assert await ws.receive_json() == {"role": "user", "text": "hello"}
        message = await asyncio.wait_for(anext(channel.messages()), 2)
        assert message.text == "hello"
        await channel.send(Reply(text="hi"))
        assert await ws.receive_json() == {"role": "assistant", "text": "hi"}


async def test_trace_events_stream_to_the_page(served):
    channel, base = served
    async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws", origin=base) as ws:
        await channel.trace(Event(kind="step", role="direct", data={"summary": "fetch x"}, cost_usd=0.01))
        item = await ws.receive_json()
        assert item == {"type": "trace", "kind": "step", "role": "direct", "data": {"summary": "fetch x"}, "cost_usd": 0.01}


async def test_stop_sets_the_cancel_flag_and_is_not_a_message(served):
    channel, base = served
    async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws", origin=base) as ws:
        await ws.send_json({"stop": True})
        await asyncio.wait_for(channel.cancel.wait(), 2)
        await ws.send_json({"text": "next"})
        assert (await asyncio.wait_for(anext(channel.messages()), 2)).text == "next"  # stop was not queued as a request


async def test_chat_replayed_on_reconnect(served):
    channel, base = served
    await channel.send(Reply(text="earlier"))
    async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws", origin=base) as ws:
        assert await ws.receive_json() == {"role": "assistant", "text": "earlier"}


async def test_foreign_origin_is_rejected(served):
    _, base = served
    async with aiohttp.ClientSession() as session:
        with pytest.raises(aiohttp.WSServerHandshakeError) as err:
            await session.ws_connect(f"{base}/ws", origin="http://evil.example")
    assert err.value.status == 403


async def test_blank_and_malformed_messages_are_ignored(served):
    channel, base = served
    async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws", origin=base) as ws:
        await ws.send_str("not json")
        await ws.send_json({"text": "   "})
        await ws.send_json({"text": "real"})
        assert await ws.receive_json() == {"role": "user", "text": "real"}
        assert (await asyncio.wait_for(anext(channel.messages()), 2)).text == "real"
