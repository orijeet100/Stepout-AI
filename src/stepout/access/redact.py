"""Secret screening: patterns applied to text read from a file, before any model sees it. A secret becomes `[redacted]`.

This is a net, not a promise. It catches the common shapes of secrets (below) and misses what only a human would recognise:
a password described in a sentence, a key split across lines or columns by a PDF's layout, anything unusual. It is the
second layer: the block list keeps whole secret files (.env, keys, credential folders) from being opened at all (files.py).
The Reader also treats everything it reads as untrusted data, and a Run that has read a file cannot reach the web.
"""

from __future__ import annotations

import re

REDACTED = "[redacted]"

_BEGIN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")
_END = re.compile(r"-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")

# Whole-token shapes: the entire match is replaced.
_TOKENS = [
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}"),  # Anthropic
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),  # other `sk-` keys (OpenAI style, including sk-proj-...)
    re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),  # GitHub
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),  # Slack
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
]

# `password: hunter2`, `db_password=x`, `"api_key": "abc"`, `GITHUB_TOKEN=x`, `clientSecret: x`: the name stays, the value goes.
# The label must be a whole part of the name (split on _ . - or a camelCase capital), so `tokenization` and `Compass` are left alone.
_LABEL = r"(?i:pass(?:word|wd)?|secret|token|api[ _-]?key)"
_NAME = rf"(?<![A-Za-z0-9])(?:(?:[A-Za-z0-9]+[_.-]){{0,4}}{_LABEL}(?:[_.-][A-Za-z0-9]+){{0,4}}|[a-z][a-z0-9]*(?:Password|Passwd|Secret|Token|ApiKey)[A-Za-z0-9]*)(?![A-Za-z0-9])"
# After the name: an optional closing quote, then `:` or `=`; spaces and tabs only, so a label alone on a line never takes the next line.
_LABELLED = re.compile(rf"""({_NAME})(["']?[ \t]*[:=][ \t]*)("[^"\n]*"|'[^'\n]*'|[^\s,;"']+)""")


def _private_keys(text: str) -> tuple[str, int]:
    """Cut every `-----BEGIN ... PRIVATE KEY-----` block, to its END marker or, if there is none, to the end of the text.

    Done by scanning (one pass, linear), not by a regex that has to search ahead from every BEGIN: a file made of thousands of BEGIN markers
    with no END would make that quadratic.
    """
    out, at, found = [], 0, 0
    while (begin := _BEGIN.search(text, at)) is not None:
        out.append(text[at : begin.start()])
        out.append(REDACTED)
        found += 1
        end = _END.search(text, begin.end())
        if end is None:  # an unfinished block: everything after it is part of it
            return "".join(out), found
        at = end.end()
    out.append(text[at:])
    return "".join(out), found


def _labelled(text: str) -> tuple[str, int]:
    changed = 0

    def swap(match: re.Match) -> str:
        nonlocal changed
        if match.group(3) == REDACTED:  # a token an earlier pattern already replaced
            return match.group(0)
        changed += 1
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    return _LABELLED.sub(swap, text), changed


def redact(text: str) -> tuple[str, int]:
    """-> (text with secrets replaced, how many replacements were made). Running it again on its own output changes nothing."""
    text, count = _private_keys(text)
    for pattern in _TOKENS:
        text, n = pattern.subn(REDACTED, text)
        count += n
    text, n = _labelled(text)
    return text, count + n
