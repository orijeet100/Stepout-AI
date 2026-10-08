"""Fetcher: get(url) -> FetchedPage. HTTP only, network policy, size limit.

ponytail: resolves the hostname once and checks that address; doesn't guard
against DNS rebinding between check and connect. Browser's fuller network
policy (checked on every request, including ones a page starts itself) is S2.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

_MAX_BYTES = 2_000_000
MAX_HOPS = 5  # redirects followed, here and in the Browser
REDIRECTS = (301, 302, 303, 307, 308)
_TAG_RE = re.compile(r"<[^>]+>")


class FetchedPage(BaseModel):
    url: str
    text: str


class BlockedUrl(Exception):
    pass


def _check_policy(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedUrl(f"scheme not allowed: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise BlockedUrl("no host")
    if host == "localhost":
        raise BlockedUrl("localhost blocked")
    try:  # every address the host has: the connection may use any of them, not only the first
        ips = {ipaddress.ip_address(info[4][0].split("%")[0]) for info in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError, ValueError) as exc:
        raise BlockedUrl(f"could not resolve host: {host}") from exc
    for ip in ips:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise BlockedUrl(f"private/local address blocked: {ip}")


def _html_to_text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


class Fetcher:
    async def get(self, url: str) -> FetchedPage:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            for _ in range(MAX_HOPS + 1):
                # every hop: a redirect is a new request, and it may point at this machine (the chat's own history API) or a private host.
                # In a thread: a slow DNS answer must not freeze the page, Stop and the live view.
                await asyncio.to_thread(_check_policy, url)
                try:
                    response = await client.get(url, headers={"User-Agent": "stepout/0.1"})
                    if response.status_code not in REDIRECTS or "location" not in response.headers:
                        break
                    url = str(response.url.join(response.headers["location"]))
                except (httpx.InvalidURL, httpx.RemoteProtocolError) as exc:  # a model-written address, or a redirect to one, that is not an address
                    if isinstance(exc, httpx.RemoteProtocolError) and "location" not in str(exc).lower():
                        raise  # a genuine protocol error: the caller reports it as before
                    raise BlockedUrl(f"not a valid address: {url[:80]!r}") from exc
            else:
                raise BlockedUrl("too many redirects")
            response.raise_for_status()
            content = response.text[:_MAX_BYTES]
        return FetchedPage(url=str(response.url), text=_html_to_text(content))
