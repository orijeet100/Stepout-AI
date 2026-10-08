"""Links in a tainted answer. A file can tell the Assistant to end its reply with a link that holds the file's text, and the page shows markdown links
as links, so one click would send it. In a Run that has read files, a markdown link survives only if its address came from somewhere else (the User's
request, a Finding gathered before the first read, an earlier reply); otherwise it keeps its words and loses the address.

ponytail: markdown only, which is all the page turns into a link (a bare address is shown as text). If the page ever links bare addresses, this must too.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s)\]>\"'<]+")
_INLINE = re.compile(r"\[([^\]\n]*)\]\(\s*<?(https?://[^)\s>]+)>?[^)]*\)")  # [words](address) or [words](<address> "title")
_ANGLE = re.compile(r"<(https?://[^>\s]+)>")
_REFERENCE = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*<?(https?://\S+?)>?(?:[ \t].*)?$", re.M)  # [1]: address


def _norm(url: str) -> str:
    return url.rstrip(".,;:!?").rstrip("/")


def urls(text: str) -> set[str]:
    """The web addresses written in `text`."""
    return {_norm(u) for u in _URL.findall(text)}


def defang(text: str, allowed: set[str]) -> str:
    """`text` with every markdown link to an address not in `allowed` replaced by its words and `[link removed: host]`."""
    host = lambda url: urlparse(url).hostname or "?"  # noqa: E731
    text = _INLINE.sub(lambda m: m[0] if _norm(m[2]) in allowed else f"{m[1]} [link removed: {host(m[2])}]", text)
    text = _ANGLE.sub(lambda m: m[0] if _norm(m[1]) in allowed else f"[link removed: {host(m[1])}]", text)
    return _REFERENCE.sub(lambda m: m[0] if _norm(m[1]) in allowed else "", text)
