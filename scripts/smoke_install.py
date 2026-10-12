"""Smoke test for a built Stepout wheel, installed the way the README does.

Proves: `uv tool install` puts a working `stepout` script in a clean tool folder,
`stepout web` serves the page and the API, and the app keeps its data in
STEPOUT_HOME instead of the working folder.

Usage: python scripts/smoke_install.py <path-to-wheel>
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


class Smoke(Exception):
    pass


def get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.read().decode("utf-8")


def check_app(port):
    if '<div id="root">' not in get(port, "/"):
        raise Smoke('the page at / has no <div id="root">')
    if json.loads(get(port, "/api/conversations")) != []:
        raise Smoke("/api/conversations is not []")


def run(wheel, tmp, log_path):
    data_before = os.path.exists("data")
    install = subprocess.run(
        ["uv", "tool", "install", "--python", "3.12", str(wheel)],
        env={**os.environ, "UV_TOOL_DIR": str(tmp / "tools"), "UV_TOOL_BIN_DIR": str(tmp / "bin")},
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        raise Smoke(f"uv tool install failed:\n{install.stdout}{install.stderr}")

    exe = tmp / "bin" / ("stepout.exe" if sys.platform == "win32" else "stepout")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    env.update(STEPOUT_HOME=str(tmp / "home"), STEPOUT_PORT=str(port), PYTHONUTF8="1")
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(exe), "web"], env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT
        )
        try:
            deadline = time.monotonic() + 60
            while True:
                if proc.poll() is not None:
                    raise Smoke(f"stepout exited early with code {proc.returncode}")
                try:
                    check_app(port)
                    break
                except OSError as e:  # not listening yet
                    if time.monotonic() > deadline:
                        raise Smoke(f"not ready after 60 s: {e}")
                time.sleep(0.5)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    if not (tmp / "home").is_dir():
        raise Smoke("STEPOUT_HOME was not created")
    if not data_before and os.path.exists("data"):
        raise Smoke("stepout wrote a 'data' folder into the working folder")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    wheel = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        log_path = Path(tmp) / "stepout.log"
        try:
            run(wheel, Path(tmp), log_path)
        except (Smoke, OSError, ValueError) as e:
            print(f"smoke: FAILED: {e}")
            if log_path.exists():
                print("--- app log ---")
                print(log_path.read_text(encoding="utf-8", errors="replace"))
            return 1
    print(f"smoke: ok ({wheel.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
