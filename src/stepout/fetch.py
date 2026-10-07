"""Fetcher: get(url) -> FetchedPage. HTTP only, network policy, size limit.

ponytail: resolves the hostname once and checks that address; doesn't guard
against DNS rebinding between check and connect. Browser's fuller network
policy (checked on every request, including ones a page starts itself) is S2.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

_MAX_BYTES = 2_000_000
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
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
    except (socket.gaierror, ValueError) as exc:
        raise BlockedUrl(f"could not resolve host: {host}") from exc
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise BlockedUrl(f"private/local address blocked: {ip}")


def _html_to_text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


class Fetcher:
    async def get(self, url: str) -> FetchedPage:
        _check_policy(url)
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers={"User-Agent": "stepout/0.1"})
            response.raise_for_status()
            content = response.text[:_MAX_BYTES]
        return FetchedPage(url=str(response.url), text=_html_to_text(content))
