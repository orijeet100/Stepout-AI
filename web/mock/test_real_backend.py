"""web/mock/real_backend.py must keep working as the backend's API moves: it runs, answers a normal message, declines a payment, and links a follow-up.

It broke silently when B3 changed Intake and Runner.submit, because nothing ran it. Run with the other mock tests: python -m pytest web/mock -q
"""

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

SCRIPT = Path(__file__).resolve().parent / "real_backend.py"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def say(base: str, port: int, texts: list[str]) -> list[str]:
    replies = []
    async with aiohttp.ClientSession() as http:
        async with http.post(f"{base}/api/conversations", headers={"Origin": base, "Content-Type": "application/json"}, data=b"{}") as r:
            chat = (await r.json())["id"]
        async with http.ws_connect(f"ws://127.0.0.1:{port}/ws", headers={"Origin": base}) as ws:
            for text in texts:
                await ws.send_str(json.dumps({"type": "send", "conversation_id": chat, "text": text}))
                while True:
                    frame = await asyncio.wait_for(ws.receive_json(), 15)
                    if frame.get("type") == "message" and frame["role"] == "assistant":
                        replies.append(frame["text"])
                        break
    return replies


def test_the_real_backend_demo_answers_declines_and_links_a_follow_up(tmp_path):
    port = free_port()
    proc = subprocess.Popen([sys.executable, str(SCRIPT), "--port", str(port), "--db", str(tmp_path / "demo.db"), "--delay", "0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        end = time.time() + 20
        while time.time() < end:
            with socket.socket() as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.2)
        answer, declined, followup = asyncio.run(say(f"http://127.0.0.1:{port}", port, ["2 + 3", "pay my invoice", "and what about it"]))
    finally:
        proc.terminate()
        proc.wait(10)
    assert "You said: 2 + 3" in answer and "Something went wrong" not in answer
    assert "payment" in declined.lower()
    assert "You said: and what about it" in followup
