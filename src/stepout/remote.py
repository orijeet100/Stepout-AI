"""`stepout remote`: this laptop's chat on the User's phone, through Tailscale Serve (ADR 0020, 0021).

Serve gives the laptop an HTTPS name that only the owner's own devices can reach; the server still listens on 127.0.0.1
only. Funnel (the public internet) is never used. What it sets up is written to Home's .env: the host name the guard lets in
(STEPOUT_REMOTE_HOSTS) and the owner's Tailscale login it requires (STEPOUT_REMOTE_LOGIN).

Everything here can be run again: each step looks first and repairs only what is off. `setup` is the interactive chain (install,
sign in, name, serve); `prepare` is the quiet repair-and-check the app runs at every start; `report` is `stepout status`.
`run`, `find`, `ask`, `out`, `wait` and `get` are swapped in tests.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

import segno

from stepout.init import set_env

DOWNLOAD = "https://tailscale.com/download/windows"
WINGET_ID = "Tailscale.Tailscale"  # exact case: with -e, winget finds nothing for `tailscale.tailscale` (checked 2026-10-16)
_WINDOWS_EXE = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"
_NAME_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes
_PHONES = ("iOS", "android")
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # these are this laptop's own addresses: never through a proxy


def find_tailscale() -> str | None:
    """The tailscale CLI, also when the installer did not put it on PATH (a terminal opened before the install)."""
    return shutil.which("tailscale") or (str(_WINDOWS_EXE) if _WINDOWS_EXE.is_file() else None)


def get(url: str, timeout: float = 8) -> tuple[int, str]:
    """(status, body) of a GET. A refusal is a status, not an exception; no connection raises OSError."""
    try:
        with _DIRECT.open(url, timeout=timeout) as r:
            return r.status, r.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def _json(exe: str, args: list[str], run: Callable = subprocess.run) -> dict:
    try:
        done = run([exe, *args], capture_output=True, text=True, timeout=20)
        return json.loads(done.stdout or "{}")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return {}


def _identity(status: dict) -> tuple[str, str]:
    """(this laptop's HTTPS name, its owner's login) from `tailscale status --json`; "" for what is missing."""
    me = status.get("Self") or {}
    host = (me.get("DNSName") or "").rstrip(".")
    login = ((status.get("User") or {}).get(str(me.get("UserID"))) or {}).get("LoginName", "")
    return host, login


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def neutral_name(current: str, computer: str | None = None) -> str | None:
    """A new neutral name if the laptop still goes by its computer's name (often the owner's: HTTPS names land in a public
    certificate log), else None: a name already chosen, by us or the User, stays, so the phone's link stays the same."""
    if _slug(current) != _slug(computer if computer is not None else platform.node()):
        return None
    return "stepout-" + "".join(secrets.choice(_NAME_CHARS) for _ in range(4))


def _serving(exe: str, host: str, port: int, run: Callable) -> bool:
    handler = ((_json(exe, ["serve", "status", "--json"], run).get("Web") or {}).get(f"{host}:443") or {}).get("Handlers", {}).get("/", {})
    return handler.get("Proxy") == f"http://127.0.0.1:{port}"


def _serve(exe: str, port: int, run: Callable, timeout: float | None) -> bool:
    try:
        return run([exe, "serve", "--bg", "--https=443", f"http://127.0.0.1:{port}"], check=False, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:  # waiting on a consent page nobody is looking at
        return False


def setup(port: int, env_path: Path, *, ask: Callable[[str], str] = input, out: Callable[[str], None] = print, run: Callable = subprocess.run,
          find: Callable[[], str | None] = find_tailscale, wait: Callable[[float], None] = time.sleep,
          winget: Callable[[], str | None] = lambda: shutil.which("winget")) -> str | None:
    """From nothing to a served chat: install Tailscale, sign in, take a neutral name, serve, check it took. -> the phone's URL, or None."""
    if os.name != "nt":
        out("`stepout remote` is Windows-only for now.")
        return None
    if not (exe := find()):
        if winget() and ask("Tailscale (free) joins your phone to this laptop, and it is not installed. Install it now with winget? [Y/n] ").strip().lower() in ("", "y", "yes"):
            if run(["winget", "install", "--id", WINGET_ID, "-e", "--accept-package-agreements", "--accept-source-agreements"], check=False).returncode != 0:
                out(f"winget could not install it (its message is above). Install it from {DOWNLOAD} instead.")
        else:
            out(f"Next: install Tailscale from {DOWNLOAD}")
        out("Waiting for Tailscale to be installed... (Ctrl+C to stop)")
        while not (exe := find()):
            wait(3)
    if (status := _json(exe, ["status", "--json"], run)).get("BackendState") != "Running":
        out("Next: sign in to Tailscale. Open Tailscale from the Start menu (or its icon by the clock) and log in with Google, Microsoft or similar.\nWaiting for you to sign in... (Ctrl+C to stop)")
        while (status := _json(exe, ["status", "--json"], run)).get("BackendState") != "Running":
            wait(3)
    if new := neutral_name((status.get("Self") or {}).get("HostName", "")):
        out(f"Naming this laptop {new} for your phone (HTTPS names are public, so not your real name).")
        run([exe, "set", f"--hostname={new}"], check=False)
        for _ in range(20):  # the new name has to reach the DNS name before Serve is keyed to it
            if ((status := _json(exe, ["status", "--json"], run)).get("Self") or {}).get("HostName") == new:
                break
            wait(1.5)
    host, login = _identity(status)
    if not host or not login:
        out("Tailscale did not give this laptop an HTTPS name. Turn on MagicDNS and HTTPS in the Tailscale admin console (DNS page), then run `stepout remote` again.")
        return None
    if not _serving(exe, host, port, run):
        out("Turning on Tailscale Serve for the chat (the first time, Tailscale may ask you to allow HTTPS in your browser: do that, and this continues)...")
        if not _serve(exe, port, run, None) or not _serving(exe, host, port, run):
            out("Tailscale Serve did not start (its message is above). Fix that, then run `stepout remote` again.")
            return None
    set_env(env_path, "STEPOUT_REMOTE_HOSTS", host)
    set_env(env_path, "STEPOUT_REMOTE_LOGIN", login)
    return f"https://{host}/"


def verify(host: str, *, fetch: Callable = get, wait: Callable[[float], None] = time.sleep, tries: int = 10) -> str | None:
    """None if https://<host>/ answers as Stepout from this laptop, else why not. Retries: the first certificate takes a moment."""
    problem = ""
    for attempt in range(tries):
        try:
            code, body = fetch(f"https://{host}/api/health")
        except OSError as exc:
            problem = f"this laptop could not open https://{host}/ ({exc})."
        else:
            if code == 200 and '"stepout"' in body:
                return None
            if code == 403:
                return "Stepout refused the request: it was started before phone access was set up. Stop it (`stepout stop`) and start it again."
            problem = f"https://{host}/ answered {code} instead of Stepout."
        if attempt < tries - 1:
            wait(3)
    return problem


def prepare(port: int, host: str, *, run: Callable = subprocess.run, find: Callable[[], str | None] = find_tailscale,
            fetch: Callable = get, wait: Callable[[float], None] = time.sleep) -> str | None:
    """At every start, quietly: Tailscale is there and signed in, Serve points at this port, and the phone address answers. -> a problem, or None."""
    if not (exe := find()):
        return "Tailscale is not installed. Run `stepout remote`."
    status = _json(exe, ["status", "--json"], run)
    if status.get("BackendState") != "Running":
        return "Tailscale is not running or not signed in. Open Tailscale and sign in."
    if _identity(status)[0] != host:
        return f"this laptop is now called {_identity(status)[0] or 'something else'}, not {host}. Run `stepout remote` to set the phone link up again."
    if not _serving(exe, host, port, run) and not (_serve(exe, port, run, 60) and _serving(exe, host, port, run)):
        return "Tailscale Serve is off and could not be turned on. Run `stepout remote`."
    return verify(host, fetch=fetch, wait=wait)


def report(port: int, host: str, *, run: Callable = subprocess.run, find: Callable[[], str | None] = find_tailscale, fetch: Callable = get) -> list[tuple[bool | None, str]]:
    """`stepout status`, the phone half: (ok, line) rows. ok None is information, not a fault."""
    if not host:
        return [(None, "Phone access is not set up (`stepout remote` sets it up).")]
    if not (exe := find()):
        return [(False, "Tailscale is not installed: run `stepout remote`.")]
    status = _json(exe, ["status", "--json"], run)
    if status.get("BackendState") != "Running":
        return [(False, f"Tailscale is {status.get('BackendState') or 'not responding'}: open Tailscale and sign in.")]
    me, name = status.get("Self") or {}, _identity(status)[0]
    rows: list[tuple[bool | None, str]] = [(name == host, f"This laptop is {name}" if name == host else f"This laptop is {name}, not {host}: run `stepout remote`.")]
    rows.append((_serving(exe, name, port, run), "Serve forwards the phone address to this chat" if _serving(exe, name, port, run) else "Serve is not forwarding to this chat: restart Stepout, or run `stepout remote`."))
    phones = [p for p in (status.get("Peer") or {}).values() if p.get("UserID") == me.get("UserID") and p.get("OS") in _PHONES]
    if not phones:
        rows.append((False, "No phone is signed in to your Tailscale: install the app on it and sign in with the same account."))
    for phone in phones:
        up = bool(phone.get("Online"))
        label = phone.get("HostName") if phone.get("HostName") not in ("", "localhost", None) else f"({phone.get('OS')})"  # iOS reports its name as "localhost"
        rows.append((up, f"Phone {label} is {'online' if up else 'offline: open the Tailscale app and switch it on'}"))
    try:
        code, body = fetch(f"https://{host}/api/health")
        rows.append((code == 200 and '"stepout"' in body, f"The phone address answers: https://{host}/" if code == 200 else f"The phone address answered {code}: restart Stepout."))
    except OSError:
        rows.append((False, f"The phone address https://{host}/ does not answer: is Stepout running?"))
    return rows


def show_qr(url: str) -> None:
    qr = segno.make(url, error="m")
    try:
        qr.terminal(compact=True)  # half blocks: a quarter of the size
    except UnicodeEncodeError:  # a console that cannot draw them
        qr.terminal()


def off(env_path: Path, *, run: Callable = subprocess.run, find: Callable[[], str | None] = find_tailscale, out: Callable[[str], None] = print) -> None:
    if exe := find():
        run([exe, "serve", "--https=443", "off"], check=False)
    set_env(env_path, "STEPOUT_REMOTE_HOSTS", "")
    set_env(env_path, "STEPOUT_REMOTE_LOGIN", "")
    out("Phone access is off: this laptop's chat is reachable from this laptop only.")


def keep_awake() -> None:
    """While this process runs, Windows does not idle-sleep (a closed lid still does). Ends with the process."""
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
