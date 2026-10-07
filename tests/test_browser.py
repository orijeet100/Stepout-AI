"""The Browser against a real headless Chrome and two local web servers.

`site` plays the public web; `private` plays a router or local service: the test policy blocks its port,
and the assertions are that it never receives a single request, however the page tries to reach it.
"""

import asyncio
import os
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from aiohttp import web

from stepout.browser import Browser
from stepout.fetch import BlockedUrl

pytestmark = pytest.mark.skipif(not os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), reason="needs Chrome")


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
    site.router.add_get("/redir", redirect(f"{B}/secret"))
    site.router.add_get("/redir-ok", redirect("/about"))
    site.router.add_get("/chain", redirect("/redir"))  # public -> public -> private
    site.router.add_get("/file", lambda r: web.Response(text="data", headers={"Content-Disposition": "attachment; filename=x.txt"}))
    runner_a, port_a = await serve(site)

    def policy(url):
        if urlparse(url).port == port_b:
            raise BlockedUrl("private address")

    browser = Browser(shots=tmp_path / "shots", policy=policy)
    yield SimpleNamespace(browser=browser, a=f"http://127.0.0.1:{port_a}", b=B, hits=hits, shots=tmp_path / "shots")
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
