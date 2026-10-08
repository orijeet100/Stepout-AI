"""Files: how the Assistant looks at the User's disk. Metadata only (names, sizes, dates, counts); read-only; Windows paths.

Every path the model supplies goes through `_resolve`: shape check, then the *real* path
(links, junctions and 8.3 short names resolved), then the block list, then the Grants.
Walks never follow links, skip blocked folders, and stop on a clock or when the User presses Stop.
Block list ("Off-limits") is fixed in code: no grant or prompt can widen it (ADR 0008).
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import time
import tomllib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Callable

WALK_SECONDS = 60
LIST_LIMIT = 100
FIND_LIMIT = 30
FIND_MAX_HITS = 5000

_REPO = os.path.normcase(str(Path(__file__).resolve().parents[2]))  # the Assistant's own folder (.env, data/)

_PREFIXES = (_REPO, r"c:\windows", r"c:\program files", r"c:\program files (x86)", r"c:\programdata")
_FRAGMENTS = (  # whole path segments; matched anywhere in a path
    r"\.ssh", r"\.aws", r"\.azure", r"\.gnupg", r"\.kube", r"\.docker",
    r"\appdata\local\google\chrome\user data", r"\appdata\local\microsoft\edge\user data",
    r"\appdata\roaming\mozilla\firefox", r"\appdata\local\bravesoftware",
    r"\appdata\roaming\microsoft\credentials", r"\appdata\local\microsoft\credentials",
    r"\appdata\roaming\microsoft\protect", r"\appdata\roaming\microsoft\vault", r"\appdata\local\microsoft\vault",
    r"\appdata\roaming\1password", r"\appdata\local\1password", r"\appdata\roaming\bitwarden", r"\appdata\roaming\keepassxc",
    r"\$recycle.bin", r"\system volume information",
)
_NAMES = (
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "*.ppk", "id_rsa*", "id_ed25519*", "id_ecdsa*",
    "*.kdbx", "wallet.dat", ".git-credentials", ".npmrc", ".netrc", ".pypirc",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys", "ntuser.dat*",
)
_NAME_RE = re.compile("|".join(fnmatch.translate(n) for n in _NAMES), re.I)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def blocked_reason(path: str) -> str | None:
    """Why a (real) path is off-limits, or None."""
    low = os.path.normcase(path).rstrip("\\")
    seg = low + "\\"
    if any(seg.startswith(p + "\\") for p in _PREFIXES):
        return "system or Assistant folder"
    if any(f + "\\" in seg for f in _FRAGMENTS):
        return "credential or browser-profile folder"
    if _NAME_RE.match(low.rsplit("\\", 1)[-1]):
        return "key or secret file"
    return None


def _clean(name: str, limit: int = 120) -> str:
    """File names are written by anyone and end up in the model's context: no control characters, bounded length."""
    return _CONTROL_RE.sub("?", name)[:limit]


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _under(low: str, root: str) -> bool:
    root = root.rstrip("\\")
    low = low.rstrip("\\")
    return low == root or low.startswith(root + "\\")


@dataclass(frozen=True)
class Grant:
    root: str  # real, normcased
    mode: str  # "metadata" | "read"; metadata operations work in either, `read` is for the Reader (M4)


def load_grants(path: Path) -> list[Grant]:
    """grants.toml: only the User edits it. Missing file = no access. A bad mode refuses to start."""
    if not path.exists():
        return []
    grants = []
    for g in tomllib.loads(path.read_text(encoding="utf-8")).get("grant", []):
        mode = g.get("mode", "metadata")
        if mode not in ("metadata", "read"):
            raise ValueError(f"{path}: unknown grant mode {mode!r}")
        grants.append(Grant(os.path.normcase(os.path.realpath(g["path"])), mode))
    return grants


class _Walk:
    """Depth-first scan: yields (DirEntry, is_dir). Never follows links; skips blocked entries (counted in .hidden)."""

    def __init__(self, root: str, cancelled: Callable[[], bool]) -> None:
        self._root, self._cancelled = root, cancelled
        self._deadline = time.monotonic() + WALK_SECONDS
        self.hidden = 0
        self.stopped = ""  # why it ended early; "" = it finished

    def _halt(self) -> bool:
        if self._cancelled():
            self.stopped = "you pressed Stop"
        elif time.monotonic() > self._deadline:
            self.stopped = f"the {WALK_SECONDS}s limit"
        return bool(self.stopped)

    def __iter__(self):
        stack, seen = [self._root], 0
        while stack:
            if self._halt():
                return
            try:
                it = os.scandir(stack.pop())
            except OSError:  # no permission, vanished: skip it
                continue
            with it:
                for e in it:
                    seen += 1
                    if seen % 5000 == 0 and self._halt():
                        return
                    try:
                        if e.is_symlink() or e.is_junction():
                            continue
                        if _NAME_RE.match(e.name):
                            self.hidden += 1
                            continue
                        is_dir = e.is_dir(follow_symlinks=False)
                        if is_dir and blocked_reason(e.path):
                            self.hidden += 1
                            continue
                        if is_dir:
                            stack.append(e.path)
                        yield e, is_dir
                    except OSError:
                        continue


def _terms(pattern: str) -> list[str]:
    """Quoted words or comma/pipe-separated words are alternatives; a bare phrase is one term. Quotes are never part of a name."""
    quoted = re.findall(r"\"([^\"]+)\"|'([^']+)'", pattern)
    parts = [a or b for a, b in quoted] or re.split(r"[,|]", pattern)
    return [t for t in (p.strip().strip("\"'").strip() for p in parts) if t]


def _date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


class Files:
    def __init__(self, grants: list[Grant] | None = None) -> None:
        self._grants = grants or []

    @classmethod
    def from_config(cls, path: Path) -> Files:
        return cls(load_grants(path))

    async def run(self, op: str, path: str, pattern: str | None = None, cancelled: Callable[[], bool] = lambda: False) -> str:
        # In a thread: a big walk must not freeze the event loop (the web page, Stop).
        return await asyncio.to_thread(self._run, op, path, pattern, cancelled)

    def _run(self, op: str, path: str, pattern: str | None, cancelled: Callable[[], bool]) -> str:
        real, why = self._resolve(path)
        if real is None:
            return f"Denied: {why}"
        if op == "list":
            return self._list(real)
        if op == "count":
            return self._count(real, cancelled)
        if op == "find":
            if not _terms(pattern or ""):
                return "Error: find needs a pattern"
            if os.path.splitdrive(real)[1] in ("", "\\"):  # a drive root
                return (
                    "Denied: find on a whole drive is too broad and cannot finish. `list` the drive, then find inside the "
                    "folders most likely to hold it. If you cannot tell where to look, say so, so the User can be asked."
                )
            return self._find(real, pattern.strip(), cancelled)
        return f"Error: unknown operation {op!r}"

    def _resolve(self, raw: str) -> tuple[str | None, str]:
        p = raw.strip().strip('"')
        win = PureWindowsPath(p)
        # a plain local absolute path only: no relative, UNC/device (`\\server`, `\\?\`), alternate stream (`:`) or `..`
        if not re.fullmatch(r"[A-Za-z]:", win.drive) or not win.is_absolute() or ".." in win.parts or ":" in p[2:]:
            return None, "not a plain absolute local path (no relative, network, device, stream or .. paths)"
        real = os.path.realpath(p)  # links, junctions and 8.3 short names resolved BEFORE any check
        if not os.path.exists(real):
            return None, "path does not exist"
        low = os.path.normcase(real)
        if reason := blocked_reason(low):
            return None, f"off-limits ({reason}); this is a fixed safety rule, not a permissions problem, so do not suggest workarounds"
        if not any(_under(low, g.root) for g in self._grants):
            if not self._grants:  # nothing is allowed because nothing was set up: a first-run problem, not a refusal
                return None, "outside every grant (no folders are allowed yet: copy grants.example.toml to data/config/grants.toml and list the folders to allow; only the User can do that, so tell them)"
            return None, "outside every grant; the User has not allowed this location, so do not suggest workarounds"
        return real, ""

    def resolve_readable(self, raw: str) -> tuple[str | None, str]:
        """`_resolve` for reading a file's CONTENTS: the same refusals, and the path must lie under a grant in `read` mode (a `metadata`
        grant allows names, sizes and counts only) and be a file. -> (real path, "") or (None, why)."""
        real, why = self._resolve(raw)
        if real is None:
            return None, why
        low = os.path.normcase(real)
        if not any(g.mode == "read" and _under(low, g.root) for g in self._grants):
            return None, "the User allowed this location for names, sizes and counts only, not for reading contents, so do not suggest workarounds"
        if not os.path.isfile(real):
            return None, "not a file (use `files` to look at a folder)"
        return real, ""

    def _list(self, real: str) -> str:
        if os.path.isfile(real):
            st = os.stat(real)
            return f"file  {_clean(real)}  {_size(st.st_size)}  {_date(st.st_mtime)}"
        rows, hidden, links = [], 0, 0
        with os.scandir(real) as it:
            for e in it:
                try:
                    if e.is_symlink() or e.is_junction():
                        links += 1
                    elif blocked_reason(e.path):
                        hidden += 1
                    else:
                        st = e.stat(follow_symlinks=False)
                        rows.append((not e.is_dir(follow_symlinks=False), e.name.lower(), e.name, st))
                except OSError:
                    continue
        rows.sort(key=lambda r: (r[0], r[1]))
        lines = [f"{_clean(real)}: {len(rows):,} entries ({min(len(rows), LIST_LIMIT)} shown), {hidden} hidden by the block list, {links} links skipped"]
        for is_file, _, name, st in rows[:LIST_LIMIT]:
            lines.append(f"file  {_clean(name)}  {_size(st.st_size)}  {_date(st.st_mtime)}" if is_file else f"dir   {_clean(name)}  {_date(st.st_mtime)}")
        return "\n".join(lines)

    def _count(self, real: str, cancelled: Callable[[], bool]) -> str:
        if os.path.isfile(real):
            return self._list(real)
        files = dirs = total = 0
        ext: Counter[str] = Counter()
        walk = _Walk(real, cancelled)
        for e, is_dir in walk:
            if is_dir:
                dirs += 1
                continue
            files += 1
            ext[os.path.splitext(e.name)[1].lower()[:12] or "(none)"] += 1
            try:
                total += e.stat(follow_symlinks=False).st_size
            except OSError:
                pass
        head = f"{_clean(real)}: {files:,} files, {dirs:,} folders, {_size(total)}"
        if walk.stopped:
            head += f"  [PARTIAL: stopped at {walk.stopped}; real totals are larger]"
        top = ext.most_common(15)
        other = files - sum(n for _, n in top)
        lines = [head, "by extension: " + " · ".join(f"{k} {n:,}" for k, n in top) + (f" · other {other:,}" if other else "")]
        if walk.hidden:
            lines.append(f"{walk.hidden:,} items hidden by the block list")
        return "\n".join(lines)

    def _find(self, real: str, pattern: str, cancelled: Callable[[], bool]) -> str:
        globs = [t.lower() if any(c in t for c in "*?[") else f"*{t.lower()}*" for t in _terms(pattern)]
        hits = []
        walk = _Walk(real, cancelled)
        for e, is_dir in walk:
            if not any(fnmatch.fnmatch(e.name.lower(), g) for g in globs):
                continue
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            hits.append((st.st_mtime, e.path, st.st_size, is_dir))
            if len(hits) >= FIND_MAX_HITS:
                walk.stopped = f"{FIND_MAX_HITS:,} matches"
                break
        hits.sort(reverse=True)  # newest first
        head = f"{len(hits):,} matches for {_clean(pattern)!r} under {_clean(real)}, newest first ({min(len(hits), FIND_LIMIT)} shown)"
        if walk.stopped:
            head += f"  [PARTIAL: stopped at {walk.stopped}]"
        lines = [head]
        for mtime, path, size, is_dir in hits[:FIND_LIMIT]:
            lines.append(f"{'dir ' if is_dir else 'file'}  {_clean(path, 250)}  {'' if is_dir else _size(size) + '  '}{_date(mtime)}")
        if walk.hidden:
            lines.append(f"{walk.hidden:,} items hidden by the block list")
        return "\n".join(lines)
