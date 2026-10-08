"""Decision and change log: one markdown file per entry in docs/log/, with a small frontmatter.

    python scripts/log.py new --kind decision --lane main --title "Short title" [--tags a,b]
    python scripts/log.py list [--kind K] [--lane L] [--tag T] [--since YYYY-MM-DD] [--grep TEXT]
    python scripts/log.py check --staged | --range main..HEAD

`check` fails when code (src/**/*.py|sql, web/src/**, web/index.html) changed without a docs/log entry in the same change.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "log"
KINDS = ("decision", "change", "contract", "term", "note")
LANES = ("main", "ui", "both", "docs")
CODE = re.compile(r"^(src/.+\.(py|sql)|web/(src/.+|index\.html))$")
ENTRY = re.compile(r"^docs/log/(?!README)[^/]+\.md$")

TEMPLATE = """---
date: {date}
kind: {kind}
lane: {lane}
status: accepted
title: {title}
tags: [{tags}]
refs: []
---

**What.**

**Why.**

**Alternatives.**

**Evidence.** (tests, commit, demo; for a change: the files touched)
"""


def parse(path: Path) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    meta = {"file": path.name}
    for line in (m.group(1) if m else "").splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def needs_entry(changed: list[str]) -> bool:
    """True when code changed and no log entry came with it."""
    paths = [p.replace("\\", "/") for p in changed]
    return any(CODE.match(p) for p in paths) and not any(ENTRY.match(p) for p in paths)


def changed_files(args) -> list[str]:
    spec = ["--cached"] if args.staged else [args.range]
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", *spec], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return out.split()


def cmd_new(args) -> int:
    date = dt.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:60]
    path = LOG / f"{date}-{slug}.md"
    if path.exists():
        print(f"exists: {path}", file=sys.stderr)
        return 1
    LOG.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(date=date, kind=args.kind, lane=args.lane, title=args.title, tags=args.tags), encoding="utf-8")
    print(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path)
    return 0


def cmd_list(args) -> int:
    for path in sorted(LOG.glob("*.md")):
        if path.name == "README.md":
            continue
        meta, text = parse(path), path.read_text(encoding="utf-8")
        if args.kind and meta.get("kind") != args.kind:
            continue
        if args.lane and meta.get("lane") not in (args.lane, "both"):
            continue
        if args.tag and args.tag not in meta.get("tags", ""):
            continue
        if args.since and meta.get("date", "") < args.since:
            continue
        if args.grep and args.grep.lower() not in text.lower():
            continue
        print(f"{meta.get('date', '?')}  {meta.get('kind', '?'):<8} {meta.get('lane', '?'):<5} {meta.get('title', path.stem)}  [{path.name}]")
    return 0


def cmd_check(args) -> int:
    if needs_entry(changed_files(args)):
        print("Code changed but no docs/log entry was added.\n  Add one:  python scripts/log.py new --kind change --lane <main|ui> --title \"...\"", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--kind", choices=KINDS, required=True)
    n.add_argument("--lane", choices=LANES, required=True)
    n.add_argument("--title", required=True)
    n.add_argument("--tags", default="")
    n.set_defaults(fn=cmd_new)
    ls = sub.add_parser("list")
    ls.add_argument("--kind", choices=KINDS)
    ls.add_argument("--lane", choices=LANES)
    ls.add_argument("--tag")
    ls.add_argument("--since")
    ls.add_argument("--grep")
    ls.set_defaults(fn=cmd_list)
    c = sub.add_parser("check")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--range")
    c.set_defaults(fn=cmd_check)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
