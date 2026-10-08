"""Browser: the headless Chrome the Browser agent reads pages with. Read-only, isolated, network-policed (FR18).

One fresh context per Run: no cookies, no logins, no downloads, no service workers. The agent can only
open a URL, follow a numbered link from the last page, or read further down the page: it cannot type,
click buttons or submit forms. Every request a page makes passes the Fetcher's network policy first, and
redirects are followed by us (a hop at a time, each one checked), never by the browser on its own.
Sources: playwright.dev/python/docs/{browsers,network} and /api/class-route (route.fetch(max_redirects=0)).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

from playwright.async_api import Error as PlaywrightError, async_playwright

from stepout.failure import Failure
from stepout.fetch import BlockedUrl, _check_policy

TEXT_CHARS = 5000  # of page text per view; `more` reads on
MAX_LINKS = 30
NAV_TIMEOUT_MS = 20_000
MAX_HOPS = 5
_REDIRECTS = (301, 302, 303, 307, 308)
VIEWPORT = {"width": 1000, "height": 700}  # the page's size, and the most a live frame may be
FRAME_QUALITY = 50  # JPEG quality of a live frame
FRAME_GAP_S = 0.26  # at least this long between two frames of a Run: four in any second (five would need 4 gaps = 1.04 s)
_log = logging.getLogger(__name__)


@dataclass
class _Session:
    context: object
    page: object
    title: str = ""
    text: str = ""  # the current page's text, so `more` needs no re-fetch
    at: int = 0
    links: list[tuple[str, str]] = field(default_factory=list)
    redirect: str | None = None  # where the last aborted navigation was heading
    verdicts: dict[str, str | None] = field(default_factory=dict)  # host -> why blocked (None = fine)
    shots: int = 0
    framing: bool = False  # live frames are being sent to on_frame
    last_frame: float = float("-inf")  # when the last one went (monotonic seconds)
    newest: bytes | None = None  # the newest frame not sent yet: the limiter keeps it so a page that then stays still still shows its last state
    timer: asyncio.TimerHandle | None = None  # wakes the limiter when the gap is over
    frame_error_logged: bool = False


class Browser:
    def __init__(
        self, shots: Path | None = None, policy: Callable[[str], None] = _check_policy, on_frame: Callable[[str, bytes], None] | None = None
    ) -> None:
        """`on_frame(run_id, jpeg)`: called for the live view, from the event loop, at most four times a second per Run, only while a Run's
        page exists. It must not block. If it raises, the error is logged once and the Run carries on. None (the default) means no capture."""
        self._shots, self._policy, self._on_frame = shots, policy, on_frame
        self._pw = self._chrome = None
        self._sessions: dict[str, _Session] = {}

    async def run(self, run_id: str, op: str, url: str | None = None, link: int | None = None) -> tuple[str, str | None]:
        """-> (what the agent sees, screenshot path relative to the shots folder, if any)."""
        try:
            s = self._sessions.get(run_id) or await self._open_session(run_id)
            if op == "open":
                if not url:
                    return "Error: open needs a url", None
                await self._goto(s, url)
            elif op == "click":
                if not 1 <= (link or 0) <= len(s.links):
                    return f"Error: no link {link} on this page (links are numbered 1-{len(s.links)}); open a page first", None
                await self._goto(s, s.links[link - 1][1])
            elif op == "more":
                s.at += TEXT_CHARS
                return (self._render(s, with_links=False) if s.at < len(s.text) else "No more text on this page."), None
            else:
                return f"Error: unknown operation {op!r}", None
            await self._read(s)
            return self._render(s), await self._shot(s, run_id)
        except BlockedUrl as exc:
            return f"Blocked: {exc}. Pages on private or local addresses cannot be opened.", None
        except PlaywrightError as exc:
            return f"Error: could not load the page ({str(exc).splitlines()[0][:200]}).", None

    async def close(self, run_id: str) -> None:
        if s := self._sessions.pop(run_id, None):
            await self._stop_frames(s)
            await s.context.close()

    async def aclose(self) -> None:
        for run_id in list(self._sessions):
            await self.close(run_id)
        if self._chrome:
            await self._chrome.close()
            await self._pw.stop()
            self._pw = self._chrome = None

    async def _start_chrome(self) -> None:
        """The installed Chrome, headless: nothing to download. Not installed, or not startable: say so in a line."""
        try:
            self._pw = self._pw or await async_playwright().start()
            self._chrome = await self._pw.chromium.launch(channel="chrome", headless=True)
        except PlaywrightError as exc:
            text = str(exc).strip()
            missing = "is not found" in text or "doesn't exist" in text
            detail = (text.splitlines() or ["no detail"])[0][:150]
            raise Failure("chrome", "Chrome is not installed. Install Google Chrome, then try again." if missing else f"Chrome could not be started ({detail}). Try again.") from exc

    async def _open_session(self, run_id: str) -> _Session:
        if self._chrome is None or not self._chrome.is_connected():  # the first Run, or Chrome has died since
            self._sessions.clear()  # their pages died with it
            await self._start_chrome()
        context = await self._chrome.new_context(
            accept_downloads=False, service_workers="block", viewport=VIEWPORT
        )
        context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        s = _Session(context, await context.new_page())
        await context.route("**/*", lambda route: self._gate(route, s))
        await context.route_web_socket("**/*", lambda ws: ws.close())  # pages have no business opening sockets
        if self._on_frame is not None:
            await self._start_frames(s, run_id)  # before the first page is opened, so the load is seen
        self._sessions[run_id] = s
        return s

    async def _start_frames(self, s: _Session, run_id: str) -> None:
        """Send the page's frames to on_frame until the Run's browser closes. Frames are for looking at: nothing here may stop a browse action."""

        def send() -> None:
            s.timer = None
            if not s.framing or s.newest is None:
                return
            wait = s.last_frame + FRAME_GAP_S - time.monotonic()
            if wait > 0:  # too soon (or a timer that fired a hair early): the newest frame waits for its turn
                s.timer = asyncio.get_running_loop().call_later(wait, send)
                return
            jpeg, s.newest, s.last_frame = s.newest, None, time.monotonic()
            try:
                self._on_frame(run_id, jpeg)
            except Exception:
                if not s.frame_error_logged:
                    s.frame_error_logged = True
                    _log.warning("on_frame raised for run %s; the Run carries on and further errors are not logged", run_id, exc_info=True)

        def on_frame(frame: dict) -> None:
            # Runs inside Playwright's own event dispatch: an exception escaping here would surface in the Run's next page call (tested), so none may.
            # ponytail: Chrome makes about 25 frames a second on an animated page and we keep 4; the rest are encoded for nothing. Ceiling: CPU while a
            # page animates. The fix, if it matters, is raw CDP Page.startScreencast with everyNthFrame instead of page.screencast.
            try:
                s.newest = frame["data"]
                if s.timer is None:
                    send()
            except Exception:
                _log.warning("a live frame could not be read for run %s", run_id, exc_info=True)

        s.framing = True  # frames may arrive before start() returns
        try:
            await s.page.screencast.start(on_frame=on_frame, quality=FRAME_QUALITY, size=VIEWPORT)
        except Exception:
            s.framing = False
            _log.warning("live frames could not start for run %s; browsing goes on without them", run_id, exc_info=True)

    async def _stop_frames(self, s: _Session) -> None:
        if not s.framing:
            return
        s.framing, s.newest = False, None
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        try:
            await s.page.screencast.stop()
        except Exception:  # the context is closed next either way
            pass

    async def _allowed(self, s: _Session, url: str) -> None:
        host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"  # host AND port: the policy may differ per port
        if host not in s.verdicts:
            try:
                await asyncio.to_thread(self._policy, url)  # DNS lookup: off the event loop
                s.verdicts[host] = None
            except BlockedUrl as exc:
                s.verdicts[host] = str(exc)
        if s.verdicts[host]:
            raise BlockedUrl(s.verdicts[host])

    async def _gate(self, route, s: _Session) -> None:
        """Every request the page makes: policy first, then fetched here so a redirect can't be followed unchecked."""
        request = route.request
        if request.resource_type == "media":  # video and audio: heavy, and the agent reads text
            return await route.abort()
        try:
            await self._allowed(s, request.url)
            response = await route.fetch(max_redirects=0)
        except (BlockedUrl, PlaywrightError):
            return await route.abort()
        if response.status in _REDIRECTS:
            if request.resource_type == "document" and request.frame.parent_frame is None and "location" in response.headers:
                s.redirect = urljoin(request.url, response.headers["location"])
                return await route.fulfill(status=200, content_type="text/html", body="")  # _goto checks and follows the hop
            return await route.abort()  # ponytail: subresource redirects (e.g. a CDN hop) are dropped, not followed
        await route.fulfill(response=response)

    async def _goto(self, s: _Session, url: str) -> None:
        for _ in range(MAX_HOPS):
            await self._allowed(s, url)  # every hop, before any request is made
            s.redirect = None
            await s.page.goto(url)
            if s.redirect is None:
                return
            url = s.redirect  # the hop is checked at the top of the loop, before any request is made
        raise BlockedUrl("too many redirects")

    async def _read(self, s: _Session) -> None:
        s.title = await s.page.title()
        s.text = re.sub(r"\s+", " ", await s.page.inner_text("body")).strip()
        s.at = 0
        found = await s.page.eval_on_selector_all("a[href]", "els => els.map(e => [e.innerText.trim().slice(0, 80), e.href])")
        seen: set[str] = set()
        s.links = []
        for label, href in found:
            if href.startswith(("http://", "https://")) and href not in seen:
                seen.add(href)
                s.links.append((label or href, href))
        s.links = s.links[:MAX_LINKS]

    def _render(self, s: _Session, with_links: bool = True) -> str:
        end = s.at + TEXT_CHARS
        more = f"; {len(s.text) - end:,} more chars: use `more`" if end < len(s.text) else ""
        out = [f"URL: {s.page.url}", f"Title: {s.title}", f"Text (chars {s.at}-{min(end, len(s.text))} of {len(s.text):,}{more}):", s.text[s.at:end]]
        if with_links and s.links:
            out.append("Links (use `click` with the number):")
            out += [f"[{i}] {label} -> {href}" for i, (label, href) in enumerate(s.links, 1)]
        return "\n".join(out)

    async def _shot(self, s: _Session, run_id: str) -> str | None:
        if self._shots is None:
            return None
        s.shots += 1
        rel = f"{run_id}/{s.shots}.jpg"
        path = self._shots / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(await s.page.screenshot(type="jpeg", quality=50))
        return rel
