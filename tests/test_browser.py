"""The Browser against a real headless Chrome and two local web servers.

`site` plays the public web; `private` plays a router or local service: the test policy blocks its port,
and the assertions are that it never receives a single request, however the page tries to reach it.
"""

import asyncio
import contextlib
import logging
import os
import time
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from aiohttp import web

from stepout.browser import Browser
from stepout.fetch import BlockedUrl

pytestmark = pytest.mark.skipif(not os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), reason="needs Chrome")


ANIMATED = (
    '<title>TITLE</title><body><h1 id="n">0</h1><a href="NEXT">next</a><script>let i = 0; setInterval(() => {'
    'document.getElementById("n").textContent = ++i; document.body.style.background = "hsl(" + (i * 9 % 360) + ",70%,80%)"}, 40)</script>'
)


async def serve(app) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    return runner, runner.addresses[0][1]


@pytest.fixture
async def world(tmp_path):
    hits: list[str] = []  # everything the private server is ever asked

    async def private_any(request):
        hits.append(request.path)
        return web.Response(text="SECRET")

    private = web.Application()
    private.router.add_route("*", "/{tail:.*}", private_any)
    runner_b, port_b = await serve(private)
    B = f"http://127.0.0.1:{port_b}"

    def html(body):
        return lambda request: web.Response(text=body, content_type="text/html")

    def redirect(to):
        async def handler(request):
            raise web.HTTPFound(to)

        return handler

    site = web.Application()
    site.router.add_get("/", html(f'<title>Home</title><h1>Welcome</h1><p>Hello reader</p><a href="/about">About us</a> <a href="/redir">Redirector</a> <a href="{B}/secret">Direct</a> <a href="javascript:alert(1)">js</a> <a href="/about">again</a>'))
    site.router.add_get("/about", html(f'<title>About</title><p>About page</p><img src="{B}/pixel.png"><script>new WebSocket("ws://127.0.0.1:{port_b}/ws"); fetch("{B}/xhr").catch(() => {{}});</script>'))
    site.router.add_get("/long", html("<title>Long</title><p>" + "word " * 3000 + "</p>"))
    site.router.add_get("/live", html(ANIMATED.replace("TITLE", "Live").replace("NEXT", "/live2")))  # changes every 40 ms: Chrome makes ~25 frames a second
    site.router.add_get("/live2", html(ANIMATED.replace("TITLE", "Live two").replace("NEXT", "/live")))
    site.router.add_get("/redir", redirect(f"{B}/secret"))
    site.router.add_get("/redir-ok", redirect("/about"))
    site.router.add_get("/chain", redirect("/redir"))  # public -> public -> private
    site.router.add_get("/file", lambda r: web.Response(text="data", headers={"Content-Disposition": "attachment; filename=x.txt"}))
    runner_a, port_a = await serve(site)

    def policy(url):
        if urlparse(url).port == port_b:
            raise BlockedUrl("private address")

    browser = Browser(shots=tmp_path / "shots", policy=policy)
    yield SimpleNamespace(browser=browser, a=f"http://127.0.0.1:{port_a}", b=B, hits=hits, shots=tmp_path / "shots", policy=policy)
    await browser.aclose()
    await runner_a.cleanup()
    await runner_b.cleanup()


async def test_open_follow_a_link_and_read_on(world):
    b = world.browser
    view, shot = await b.run("r1", "open", f"{world.a}/")
    assert "Title: Home" in view and "Hello reader" in view
    assert "[1] About us ->" in view and "javascript" not in view  # only http(s) links, numbered
    assert view.count("/about") == 1  # duplicates dropped
    assert shot == "r1/1.jpg" and (world.shots / shot).stat().st_size > 1000  # a screenshot to look at

    view, _ = await b.run("r1", "click", link=1)
    assert view.startswith(f"URL: {world.a}/about") and "About page" in view

    view, _ = await b.run("r1", "open", f"{world.a}/long")
    assert "more chars: use `more`" in view
    more, shot = await b.run("r1", "more")
    assert shot is None and "Text (chars 5000-" in more

    assert (await b.run("r2", "click", link=1))[0].startswith("Error")  # another Run has its own, empty browser
    await b.close("r1")
    await b.close("r1")  # closing twice is fine


async def test_nothing_reaches_the_private_server_however_the_page_tries(world):
    b = world.browser
    for url in (f"{world.b}/secret", f"{world.a}/redir", f"{world.a}/chain"):  # directly, via a redirect, via a chain
        out, _ = await b.run("r", "open", url)
        assert out.startswith("Blocked"), (url, out)
    assert (await b.run("r", "open", f"{world.a}/"))[1] is not None
    out, _ = await b.run("r", "click", link=3)  # the page links straight at it
    assert out.startswith("Blocked")
    await b.run("r", "open", f"{world.a}/about")  # the page's image, fetch() and WebSocket all aim at it
    await asyncio.sleep(0.5)
    assert world.hits == []


async def test_an_allowed_redirect_is_followed(world):
    out, _ = await world.browser.run("r", "open", f"{world.a}/redir-ok")
    assert "About page" in out and f"{world.a}/about" in out


async def test_failures_are_reported_not_raised(world):
    b = world.browser
    assert (await b.run("r", "open", "http://127.0.0.1:1/"))[0].startswith("Error")  # connection refused
    assert (await b.run("r", "open", f"{world.a}/file"))[0].startswith("Error")  # downloads are off
    assert (await b.run("r", "open"))[0].startswith("Error")
    assert (await b.run("r", "scroll"))[0].startswith("Error")
    await b.run("r", "open", f"{world.a}/")
    assert "no link 99" in (await b.run("r", "click", link=99))[0]


# --- live frames (Browser(on_frame=...)) against real Chrome --------------------------------------------------------------------


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Width and height from a JPEG's start-of-frame marker."""
    i = 2
    while i < len(data):
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(data[i + 5 : i + 7], "big")
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    raise AssertionError("not a JPEG with a frame header")


@contextlib.asynccontextmanager
async def watching(world, on_frame):
    """A second Browser over the same fake web, with a live-frame callback; closed afterwards."""
    browser = Browser(shots=world.shots, policy=world.policy, on_frame=on_frame)
    try:
        yield browser
    finally:
        await browser.aclose()


async def test_live_frames_arrive_while_a_page_loads_and_after_a_click_and_are_small_jpegs(world):
    frames = []
    async with watching(world, lambda run_id, jpeg: frames.append((run_id, jpeg))) as b:
        await b.run("r1", "open", f"{world.a}/")
        await asyncio.sleep(0.5)
        first = len(frames)
        assert first >= 1 and {run_id for run_id, _ in frames} == {"r1"}  # a still page paints at least once
        await b.run("r1", "click", link=1)  # the About page: different pixels
        await asyncio.sleep(0.6)
        assert len(frames) > first and frames[-1][1] != frames[0][1]  # the frame after the click shows the new page
    for _, jpeg in frames:
        assert jpeg[:3] == b"\xff\xd8\xff"  # a JPEG
        width, height = jpeg_size(jpeg)
        assert width <= 1000 and height <= 700  # never larger than the viewport


async def test_each_run_sends_at_most_four_frames_a_second_even_on_a_page_that_animates(world):
    times = {"r1": [], "r2": []}
    async with watching(world, lambda run_id, jpeg: times[run_id].append(time.monotonic())) as b:
        await b.run("r1", "open", f"{world.a}/live")
        await b.run("r2", "open", f"{world.a}/live")
        await asyncio.sleep(1.6)
        for run_id, stamps in times.items():
            assert len(stamps) >= 3, run_id  # they flow (Chrome would give about 40 in this time)
            assert all(sum(1 for u in stamps if t <= u < t + 1.0) <= 4 for t in stamps), run_id  # four in any second
            assert all(b2 - a2 >= 0.25 for a2, b2 in zip(stamps, stamps[1:])), run_id


async def test_a_callback_that_raises_does_not_break_browsing_or_the_screenshots(world, caplog):
    def boom(run_id, jpeg):
        raise RuntimeError("the viewer is gone")

    with caplog.at_level(logging.WARNING, logger="stepout.browser"):
        async with watching(world, boom) as b:
            view, shot = await b.run("r1", "open", f"{world.a}/live")  # animated: frames keep coming while we work
            assert "Title: Live" in view and (world.shots / shot).stat().st_size > 1000
            await asyncio.sleep(0.6)
            view, shot = await b.run("r1", "click", link=1)  # Playwright would raise the callback's error here if it escaped
            assert "Title: Live two" in view and (world.shots / shot).stat().st_size > 1000
            more, _ = await b.run("r1", "more")
            assert "No more text" in more or "Text (chars" in more
    assert len([r for r in caplog.records if "on_frame raised" in r.getMessage()]) == 1  # logged once, not four times a second


async def test_without_a_callback_nothing_is_captured_and_with_one_it_stops_when_the_run_closes(world):
    await world.browser.run("plain", "open", f"{world.a}/live")
    assert world.browser._sessions["plain"].framing is False  # no callback: the screencast was never started

    frames = []
    async with watching(world, lambda run_id, jpeg: frames.append(jpeg)) as b:
        await b.run("r1", "open", f"{world.a}/live")
        assert b._sessions["r1"].framing is True
        await asyncio.sleep(0.5)
        await b.close("r1")
        seen = len(frames)
        assert seen >= 1
        await asyncio.sleep(0.8)
        assert len(frames) == seen  # none after the Run's browser closed
