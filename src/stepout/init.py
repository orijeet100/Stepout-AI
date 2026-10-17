"""Setup in the terminal, by the User: `stepout init` (the API key, then the folders) and `stepout grant` (the folders).

Only these write the key and grants.toml; the page, the model and a phone never do (ADR 0019). The key is read hidden and
never printed or logged. `ask`, `secret` and `out` are input, getpass and print, swapped in tests.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import tomllib
from pathlib import Path, PureWindowsPath
from typing import Callable

from stepout.access.files import blocked_reason

Ask = Callable[[str], str]
Out = Callable[[str], None]

KEYS_PAGE = "https://console.anthropic.com/settings/keys"
_HEADER = """# Which folders Stepout may look at. Written by `stepout grant` (run it again to change this); only you edit it.
#   mode = "metadata": names, sizes, dates and counts.   mode = "read": also the text of files (it goes to the model provider).
# The built-in block list always applies: .ssh, .env, key files, browser profiles, Windows, Program Files, Stepout's own folders.
"""
MODES = {"metadata": "names, sizes and dates only", "read": "also the text of files"}


# ---- the .env file ---------------------------------------------------------------------------------------------------


def set_env(path: Path, name: str, value: str) -> None:
    """Set `name=value` in a .env file, replacing any earlier line for it; an empty value removes the line."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.strip().startswith(f"{name}=")]
    if value:
        lines.append(f"{name}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if value:
        os.environ[name] = value  # this run sees it too
    else:
        os.environ.pop(name, None)


def check_key(key: str) -> str | None:
    """None if Anthropic accepts the key, else why not, in plain words. Listing models costs nothing."""
    import anthropic

    try:
        anthropic.Anthropic(api_key=key, max_retries=0, timeout=20).models.list(limit=1)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        return "Anthropic refused that key. Check you copied all of it, then try again."
    except anthropic.APIError:
        return None  # no network or a hiccup: the key may well be fine, and the first message will say if it is not
    return None


# ---- grants.toml -----------------------------------------------------------------------------------------------------


def read_grants(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    return [(g["path"], g.get("mode", "metadata")) for g in tomllib.loads(path.read_text(encoding="utf-8-sig")).get("grant", [])]


def write_grants(path: Path, grants: list[tuple[str, str]]) -> None:
    """The one writer of grants.toml. A path is a TOML basic string (json.dumps escapes quotes and backslashes the same way)."""
    body = "".join(f"\n[[grant]]\npath = {json.dumps(p, ensure_ascii=False)}\nmode = \"{m}\"\n" for p, m in grants)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HEADER + body, encoding="utf-8")


def checked_folder(raw: str) -> tuple[str | None, str]:
    """A folder the User typed -> (its real path, "") or (None, why not). Same shape rules as Files: a local drive path, no tricks."""
    p = raw.strip().strip('"')
    win = PureWindowsPath(p)
    if len(p) == 2 and p[1] == ":":
        p += "\\"  # "D:" means the drive, not the current folder on it
        win = PureWindowsPath(p)
    if not re.fullmatch(r"[A-Za-z]:", win.drive) or not win.is_absolute() or ".." in win.parts:
        return None, "Give a full path on this computer, like D:\\Work or D:\\"
    real = os.path.realpath(p)
    if not os.path.isdir(real):
        return None, f"{p} is not a folder on this computer."
    if why := blocked_reason(os.path.normcase(real)):
        return None, f"{real} is always off-limits ({why})."
    return real, ""


def _numbers(answer: str, top: int) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\d+", answer) if 1 <= int(n) <= top})


def _usual_folders() -> list[str]:
    places = [Path.home(), *([Path(os.environ["OneDrive"])] if os.environ.get("OneDrive") else [])]  # OneDrive may hold the real Documents
    found = [str(base / name) for name in ("Documents", "Downloads", "Desktop") for base in places]
    return [f for f in dict.fromkeys(found) if os.path.isdir(f)]


def _pick_inside(root: str, ask: Ask, out: Out) -> list[str]:
    """A drive or the profile folder is too broad to allow whole by accident: tick its top-level folders, or type its name for all of it."""
    subs, hidden = [], 0
    for e in sorted(os.scandir(root), key=lambda e: e.name.lower()):
        try:
            if not e.is_dir(follow_symlinks=False) or e.is_junction() or e.name.startswith(("$", ".")):
                continue
        except OSError:
            continue
        if blocked_reason(os.path.normcase(e.path)):
            hidden += 1
        else:
            subs.append(e.path)
    name = PureWindowsPath(root).drive if PureWindowsPath(root).name == "" else PureWindowsPath(root).name
    out(f"{root} is a whole drive or your whole profile. Its folders:" + (f" ({hidden} off-limits, not shown)" if hidden else ""))
    for i, s in enumerate(subs, 1):
        out(f"  {i:>2}. {PureWindowsPath(s).name}")
    answer = ask(f"Numbers, separated by commas (Enter for none), or type {name} to allow all of it: ").strip()
    if answer.lower() == name.lower():
        return [root]
    return [subs[i - 1] for i in _numbers(answer, len(subs))]


def _another(ask: Ask, out: Out) -> list[str]:
    while raw := ask("Folder or drive, like D:\\Work or D:\\ (Enter to skip): ").strip():
        real, why = checked_folder(raw)
        if real is None:
            out(why)
            continue
        if os.path.splitdrive(real)[1] in ("", "\\") or os.path.normcase(real) == os.path.normcase(str(Path.home())):
            return _pick_inside(real, ask, out)
        return [real]
    return []


def _mode(folder: str, ask: Ask, out: Out) -> str:
    out(f"{folder}\n  1. {MODES['metadata']} (default)\n  2. {MODES['read']}: that text goes to the model provider, and a task that reads a file cannot use the web afterwards")
    return "read" if ask("Choose 1 or 2 [1]: ").strip() == "2" else "metadata"


def grant(path: Path, ask: Ask = input, out: Out = print) -> list[tuple[str, str]]:
    """`stepout grant`: show what is allowed, remove any, add folders. Writes grants.toml (even when empty: the question was answered)."""
    if os.name != "nt":
        out("File access is Windows-only for now, so there is nothing to allow on this computer.")
        return []
    try:
        grants = read_grants(path)
    except (ValueError, KeyError, OSError) as exc:  # a half-edited file must not stand in the way of the command that repairs it
        out(f"{path} could not be read ({exc}). It will be written again from your answers below.")
        grants = []
    if grants:
        out("Stepout may look at:")
        for i, (p, m) in enumerate(grants, 1):
            out(f"  {i}. {p}  ({MODES.get(m, m)})")
        drop = _numbers(ask("Numbers to remove, separated by commas (Enter to keep all): "), len(grants))
        grants = [g for i, g in enumerate(grants, 1) if i not in drop]
    have = {os.path.normcase(p) for p, _ in grants}
    usual = [f for f in _usual_folders() if os.path.normcase(f) not in have]
    out("Which folders may Stepout look at?")
    for i, f in enumerate(usual, 1):
        out(f"  {i}. {f}")
    out(f"  {len(usual) + 1}. Another folder or drive")
    picked = _numbers(ask("Numbers, separated by commas (Enter for none): "), len(usual) + 1)
    folders = [usual[i - 1] for i in picked if i <= len(usual)]
    if len(usual) + 1 in picked:
        folders += _another(ask, out)
    for f in folders:
        if os.path.normcase(f) not in have:
            grants.append((f, _mode(f, ask, out)))
            have.add(os.path.normcase(f))
    write_grants(path, grants)
    out(f"Saved. Stepout may look at {len(grants)} folder(s); `stepout grant` changes this any time." if grants else "Saved: no folders allowed. `stepout grant` changes this any time.")
    return grants


# ---- stepout init ----------------------------------------------------------------------------------------------------


def init(env_path: Path, grants_path: Path, ask: Ask = input, secret: Ask = getpass.getpass, out: Out = print, check: Callable[[str], str | None] = check_key) -> None:
    """`stepout init`: the Anthropic key (checked before it is kept; a refused key writes nothing), then the folders. Safe to run again."""
    out(f"Stepout keeps your chats, Memory and settings in {env_path.parent}")
    if not os.environ.get("ANTHROPIC_API_KEY") or ask("An Anthropic API key is already set. Replace it? [y/N] ").strip().lower() in ("y", "yes"):
        out(f"Paste your Anthropic API key (make one at {KEYS_PAGE}). It stays hidden as you paste.")
        while key := secret("API key (Enter to skip): ").strip():
            if why := check(key):
                out(why)
                continue
            set_env(env_path, "ANTHROPIC_API_KEY", key)
            out(f"Key saved in {env_path}.")
            break
    grant(grants_path, ask, out)
