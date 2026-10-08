"""Who owns which path: the table in docs/plan/README.md as code, checked by the merge agent for each lane.

    python scripts/owners.py --lane main|ui <branch> [--base main]

Exits 1 and lists the paths if <branch>, since it left <base>, changed anything its lane does not own.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# First match wins; a path that matches nothing belongs to DEFAULT. Keep in step with docs/plan/README.md.
RULES = [
    ("web/", "ui"),  # the page, its mock server, fixtures and tests
    ("src/stepout/channels/web.py", "ui"),
    ("docs/plan/ui-worktree.md", "ui"),
    ("docs/ui-contract.md", "both"),  # changed only with a `contract` log entry
    ("docs/log/", "both"),  # one file per entry, unique names
    ("docs/STATUS.md", "both"),  # one section per lane; a path check cannot tell the sections apart
]
DEFAULT = "main"  # src/, tests/, scripts/, .githooks/, pyproject.toml, and the project-wide docs and root files


def owner(path: str) -> str:
    path = path.replace("\\", "/")
    return next((who for prefix, who in RULES if path.startswith(prefix)), DEFAULT)


def violations(lane: str, paths: list[str]) -> list[str]:
    return [p for p in paths if owner(p) not in (lane, "both")]


def changed_paths(branch: str, base: str) -> list[str]:
    """Paths the branch changed since it left base. --no-renames: the old and the new path both count."""
    out = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{branch}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lane", choices=("main", "ui"), required=True)
    p.add_argument("--base", default="main")
    p.add_argument("branch")
    args = p.parse_args(argv)
    paths = changed_paths(args.branch, args.base)
    bad = violations(args.lane, paths)
    for path in bad:
        print(f"{path}  (owned by {owner(path)}, not {args.lane})", file=sys.stderr)
    if bad:
        return 1
    print(f"ok: {len(paths)} changed path(s), all owned by {args.lane} or shared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
