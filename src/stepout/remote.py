"""`stepout remote`: this laptop's chat on the User's phone, through Tailscale Serve (ADR 0020).

Serve gives the laptop an HTTPS name that only the owner's own devices can reach; the server still listens on 127.0.0.1
only. Funnel (the public internet) is never used. What it sets up is written to Home's .env: the host name the guard lets in
(STEPOUT_REMOTE_HOSTS) and the owner's Tailscale login it requires (STEPOUT_REMOTE_LOGIN). Each step prints only the next
action and waits for it. `run`, `ask`, `out` and `wait` are swapped in tests.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import segno

from stepout.init import set_env

DOWNLOAD = "https://tailscale.com/download/windows"
_WINDOWS_EXE = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"


def find_tailscale() -> str | None:
    """The tailscale CLI, also when the installer did not put it on PATH (a terminal opened before the install)."""
    return shutil.which("tailscale") or (str(_WINDOWS_EXE) if _WINDOWS_EXE.is_file() else None)


def _status(exe: str, run: Callable = subprocess.run) -> dict:
    done = run([exe, "status", "--json"], capture_output=True, text=True, timeout=20)
    try:
        return json.loads(done.stdout or "{}")
    except ValueError:
        return {}


def _identity(status: dict) -> tuple[str, str]:
    """(this laptop's HTTPS name, its owner's login) from `tailscale status --json`; "" for what is missing."""
    me = status.get("Self") or {}
    host = (me.get("DNSName") or "").rstrip(".")
    login = ((status.get("User") or {}).get(str(me.get("UserID"))) or {}).get("LoginName", "")
    return host, login


def setup(port: int, env_path: Path, *, ask: Callable[[str], str] = input, out: Callable[[str], None] = print,
          run: Callable = subprocess.run, find: Callable[[], str | None] = find_tailscale, wait: Callable[[float], None] = time.sleep) -> str | None:
    """From nothing to a QR code: install Tailscale, sign in, name the laptop, serve the chat. -> the phone's URL, or None."""
    if os.name != "nt":
        out("`stepout remote` is Windows-only for now.")
        return None
    if not (exe := find()):
        out(f"Next: install Tailscale (free). In a terminal run:  winget install tailscale.tailscale\n  or download it from {DOWNLOAD}\nWaiting for it to be installed... (Ctrl+C to stop)")
        while not (exe := find()):
            wait(3)
    if (status := _status(exe, run)).get("BackendState") != "Running":
        out("Next: sign in to Tailscale. Open Tailscale from the Start menu (or its icon by the clock) and log in.\nWaiting for you to sign in... (Ctrl+C to stop)")
        while (status := _status(exe, run)).get("BackendState") != "Running":
            wait(3)
    name = (status.get("Self") or {}).get("HostName", "")
    out("Your phone will reach this laptop by its name. HTTPS names are published in a public certificate log, so pick a neutral one (no real name).")
    while (new := ask(f"Name [{name}]: ").strip().lower()) and new != name.lower():
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", new):
            run([exe, "set", f"--hostname={new}"], check=False)
            break
        out("Use letters, digits and dashes only.")
    out("Turning on Tailscale Serve for the chat (the first time, Tailscale may ask you to allow HTTPS in your browser)...")
    if run([exe, "serve", "--bg", "--https=443", f"http://127.0.0.1:{port}"], check=False).returncode != 0:
        out("Tailscale Serve did not start (its message is above). Fix that, then run `stepout remote` again.")
        return None
    host, login = _identity(_status(exe, run))
    if not host or not login:
        out("Tailscale did not give this laptop an HTTPS name. Turn on MagicDNS and HTTPS in the Tailscale admin console (DNS page), then run `stepout remote` again.")
        return None
    set_env(env_path, "STEPOUT_REMOTE_HOSTS", host)
    set_env(env_path, "STEPOUT_REMOTE_LOGIN", login)
    url = f"https://{host}/"
    out(f"Next, on your phone: install Tailscale from the app store, sign in as {login}, then scan this:")
    show_qr(url)
    out(f"  {url}\nOnly your own devices signed in as {login} can open it. `stepout remote off` turns it off.")
    return url


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
