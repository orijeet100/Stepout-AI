"""Links in a tainted answer. A file can tell the Assistant to end its reply with a link that holds the file's text, and the page shows markdown links
as links, so one click would send it. In a Run that has read files, a link survives only if its address came from somewhere else (the User's request,
a Finding gathered before the first read, an earlier reply).

This fails closed. It recognises ONE shape, `[words](https://address)` in lowercase with nothing odd in it, and keeps it only if the address is
allowed; a recognised link to any other address keeps its words and loses the address. Then every remaining `[` and `<` is escaped, so nothing else
can become a link, however the markup is written (nested brackets, `mailto:`, an uppercase scheme, entities, a reference definition in a quote or a
list, an angle-bracket autolink): a form this file does not know about is shown as plain text, never as a link. Bare addresses are left alone because
the page does not link them (no GFM).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s)\]>\"'<]+")
_LINK = re.compile(r"\[([^\[\]<>\n]{0,300})\]\((https?://[^\s()<>\[\]]{1,2000})\)")  # bounded on both sides: no backtracking blow-up on hostile text


def _norm(url: str) -> str:
    return url.rstrip(".,;:!?").rstrip("/")


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or "?"
    except ValueError:  # a bracketed host that is not an address
        return "?"


def urls(text: str) -> set[str]:
    """The web addresses written in `text`, bare or in markdown."""
    return {_norm(u) for u in _URL.findall(text)}


def links_in(text: str) -> set[str]:
    """The addresses of the links in `text` that the page would show as links (what `defang` keeps)."""
    return {_norm(m[2]) for m in _LINK.finditer(text)}


def defang(text: str, allowed: set[str]) -> str:
    """`text` with no markdown link except `[words](address)` to an allowed address; a link to any other keeps its words and `(link removed: host)`."""
    kept: list[str] = []

    def park(piece: str) -> str:  # set aside, so that the escaping below does not touch it
        kept.append(piece)
        return f"\x00{len(kept) - 1}\x00"

    text = _LINK.sub(lambda m: park(m[0]) if _norm(m[2]) in allowed else park(f"{m[1]} (link removed: {_host(m[2])})"), text.replace("\x00", ""))
    # backslashes first: a `\[` the model wrote must come out as an escaped backslash and an escaped bracket, not as `\\` + a live `[`
    text = text.replace("\\", "\\\\").replace("[", "\\[").replace("<", "&lt;")
    return re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m[1])], text)
