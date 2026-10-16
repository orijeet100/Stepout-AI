"""Types through Stepout's first run in a real (pseudo) Windows console, the way a person would: no key set, a wrong key refused, then skipped,
a folder chosen, the phone question answered no. Nothing real is entered (a made-up key, a folder under <root>); the made-up key is
checked with Anthropic's API, which refuses it, so this needs the network.

Needs a wheel installed into <root> (scripts/cleanroom.ps1 does that) and the `pywinpty` package, which is not a project dependency:

    uv run --no-project --with pywinpty python scripts/first_run_console.py <root> [port]

It checks that the key is never echoed, that grants.toml names the folder, that Home is <root>/home and that the chat's port is closed again
at the end. Exit code 0 means all of that held.
"""

import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

from winpty import PtyProcess

ROOT = Path(sys.argv[1]).resolve()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8792
EXE = ROOT / "bin" / "stepout.exe"
HOME = ROOT / "home"
FOLDER = ROOT / "files"
FOLDER.mkdir(parents=True, exist_ok=True)

env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
env.update(STEPOUT_HOME=str(HOME), STEPOUT_PORT=str(PORT), PYTHONUTF8="1")

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
proc = PtyProcess.spawn([str(EXE), "web"], env=env, dimensions=(40, 140))
chunks = []


def reader():
    while True:
        try:
            chunks.append(proc.read(4096))
        except EOFError:
            return


threading.Thread(target=reader, daemon=True).start()


def seen():
    return ANSI.sub("", "".join(chunks))


def fail(why):
    print(f"first run in a real console: FAILED: {why}\n---- screen so far ----\n{seen()[-1500:]}")
    proc.terminate(force=True)
    sys.exit(1)


def expect(text, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if text in seen():
            return
        time.sleep(0.2)
    fail(f"timed out waiting for {text!r}")


def say(text):
    time.sleep(0.4)
    proc.write(text + "\r")


def port_closed():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) != 0


expect("Set it up now? [Y/n]")
say("")  # Enter is yes
expect("API key (Enter to skip):")
say("sk-ant-made-up-key-0000")  # the hidden prompt: it must be refused, not kept
expect("refused that key")
expect("API key (Enter to skip):")
say("")  # skip
expect("Another folder or drive")
say(str(max(int(n) for n in re.findall(r"^\s*(\d+)\. ", seen(), re.M))))  # the last choice is "another folder"
expect("Folder or drive")
say(str(FOLDER))
expect("Choose 1 or 2")
say("")  # names only
expect("Saved. Stepout may look at 1 folder")
expect("Use Stepout from your phone too?")
say("n")
expect(f"Stepout web chat: http://127.0.0.1:{PORT}")

text = seen()
if "sk-ant-made-up" in text:
    fail("the key was echoed")
grants = (HOME / "config" / "grants.toml").read_text(encoding="utf-8")
if str(FOLDER).replace("\\", "\\\\") not in grants:  # TOML escapes each backslash
    fail(f"grants.toml does not name {FOLDER}")
if (HOME / ".env").exists() and "ANTHROPIC_API_KEY" in (HOME / ".env").read_text(encoding="utf-8"):
    fail("a refused key was written to .env")

proc.terminate(force=True)
deadline = time.time() + 10
while not port_closed():
    if time.time() > deadline:
        fail(f"port {PORT} is still open after the chat was ended")
    time.sleep(0.2)
print("first run in a real console: ok (key hidden and refused, a folder granted, phone declined, Home is under the root, port closed again)")
