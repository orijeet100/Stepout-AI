"""Composition root: wiring, the receive -> read -> submit loop."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
import webbrowser
from typing import TYPE_CHECKING, Sequence

from dotenv import load_dotenv

from stepout import init, remote
from stepout.paths import CHECKOUT, home

if TYPE_CHECKING:  # the rest is imported where it is used: `stepout status`, `stop` and `--help` must not wait for the model SDKs (seconds)
    from stepout.browser import Browser
    from stepout.domain import Reply
    from stepout.extract import Learner
    from stepout.intake import Intake
    from stepout.ledger import Ledger
    from stepout.runner import Runner

HOME = home()  # the one data folder (paths.py)
ENV_PATH = HOME / ".env"  # the key, written by `stepout init`
DB_PATH = HOME / "stepout.db"
GRANTS_PATH = HOME / "config" / "grants.toml"  # only the User edits this (`stepout grant`)
SHOTS_PATH = HOME / "runs"  # page screenshots, one folder per Run
LOGS_PATH = HOME / "logs"  # the app log (logs.py)
MEMORY_PATH = HOME / "memory"  # Persona and what was learned (memory.py)
CAPTURE_PATH = HOME / "capture"  # prompts and replies, only when STEPOUT_CAPTURE=1 (capture.py)


def make_browser(channel) -> Browser:
    """The Runs' browser. It sends live frames to the channel if the channel shows them (the web channel does; the terminal has none, so nothing is captured)."""
    from stepout.browser import Browser

    return Browser(shots=SHOTS_PATH, on_frame=getattr(channel, "live_frame", None))


def startup_notes(keys: Sequence[str] = ("ANTHROPIC_API_KEY",)) -> list[str]:
    """What is not set up yet, each with its fix: said at start, and again at first use by the thing that is missing. `keys`: the provider keys the chosen models need."""
    notes = []
    for var in keys:
        if not os.environ.get(var):
            fix = "run `stepout init` to add it" if var == "ANTHROPIC_API_KEY" else f"put {var}=... in {ENV_PATH}"
            notes.append(f"No {var}: {fix}, then restart. Until then every message gets this answer.")
    if not GRANTS_PATH.exists():
        notes.append("No folders are allowed yet: the Local File Finder and Local File Reader agents can't see your disk. Run `stepout grant` to choose which folders they may look at.")
    return notes


def web_port() -> int:
    """The web chat's port: STEPOUT_PORT if set, else PORT (the app's preview tool assigns one when 8765 is taken), else 8765 (so two checkouts can run side by side)."""
    for name in ("STEPOUT_PORT", "PORT"):
        if (value := os.environ.get(name, "")).isdigit():  # a stray PORT that is not a number (another tool's) must not crash the start
            return int(value)
    return 8765


class SavedChannel:
    """A Channel whose every incoming message and every reply is also saved as chat history (v0: text only)."""

    def __init__(self, channel, ledger: Ledger) -> None:
        self._channel, self._ledger = channel, ledger

    async def messages(self):
        async for message in self._channel.messages():
            self._ledger.save_message(message.conversation_id, "user", message.text, message_id=message.id, at=message.at)
            yield message

    async def send(self, reply: Reply) -> None:
        self._ledger.save_message(reply.conversation_id, "assistant", reply.text, reply.run_id, reply.cost_usd, message_id=reply.id, at=reply.at)  # saved first: a closed page must not lose it
        await self._channel.send(reply)


def month_cap(environ=os.environ) -> float:
    """What the app may spend in a calendar month, in dollars (STEPOUT_MONTH_CAP_USD). A starting value, not a recommendation."""
    try:
        return float(environ.get("STEPOUT_MONTH_CAP_USD", "10.00"))
    except ValueError:
        return 10.00


async def run(channel, intake: Intake, runner: Runner, month_left=None, memory=None, learner: Learner | None = None) -> None:
    """`month_left()`: dollars the month has left; at zero a message is answered with a line and costs nothing (a slash command is free and still works)."""
    from stepout import commands
    from stepout.domain import Reply, Task
    from stepout.failure import UNEXPECTED
    from stepout.intake import ChatReading, CommandReading, DeclinedReading, FailedReading, NewTask

    async for message in channel.messages():
        cid = message.conversation_id
        try:
            if month_left is not None and not message.text.strip().startswith("/") and month_left() <= 0:
                await channel.send(Reply(text=f"This month's spending limit of ${month_cap():.2f} is used up, so I have not run anything. Raise STEPOUT_MONTH_CAP_USD in .env, or wait for next month.", conversation_id=cid))
                continue
            reading = await intake.read(message)
            match reading:
                case DeclinedReading(reason=reason, alternative=alternative, cost_usd=cost):
                    await channel.send(Reply(text=f"{reason} {alternative}", conversation_id=cid, cost_usd=cost))
                case ChatReading(text=text, cost_usd=cost):
                    await channel.send(Reply(text=text, conversation_id=cid, cost_usd=cost))
                    if learner is not None:
                        await learner.learn(message)
                case FailedReading(text=text):
                    await channel.send(Reply(text=text, conversation_id=cid))
                case CommandReading(name=name, args=args):
                    said = await commands.handle(name, args, memory) if memory is not None else None
                    await channel.send(Reply(text=said if said is not None else f"Unknown command: /{name}", conversation_id=cid))
                case NewTask(request=request, previous=previous, cost_usd=cost):
                    task = Task(user_id=message.user_id, request=request, conversation_id=cid)
                    run_id = await runner.submit(task, previous, screening_cost=cost)
                    if learner is not None:
                        await learner.learn(message, run_id)  # after the reply: what the User said about themselves, kept and shown
        except Exception:  # one failed request (API error, bad key) must not end the session
            logging.exception("request failed")
            await channel.send(Reply(text=UNEXPECTED, conversation_id=cid))


async def main(web: bool = True, open_browser: bool = False, show_qr: bool = False) -> None:
    from stepout import capture as capture_mod
    from stepout import history, housekeeping, logs
    from stepout import memory as memory_mod
    from stepout.channels.cli import CliChannel
    from stepout.channels.web import StoreHistory, WebChannel
    from stepout.chats import ChatKeeper
    from stepout.extract import Extractor, Learner
    from stepout.fetch import Fetcher
    from stepout.files import Files
    from stepout.intake import Intake
    from stepout.ledger import Ledger
    from stepout.pydantic_model import PydanticModel, default_model
    from stepout.retry import RetryingModel
    from stepout.roles import HAIKU, SONNET
    from stepout.runner import Runner
    from stepout.screening import HaikuScreener
    from stepout.store import Store

    log_file = logs.configure(LOGS_PATH)
    base = default_model()
    other = isinstance(base, PydanticModel)  # a tier is re-pointed in the environment (STEPOUT_STRONG_MODEL / STEPOUT_CHEAP_MODEL)
    if other:
        print(f"Models: strong = {base.target(SONNET)}, cheap = {base.target(HAIKU)}")
    logging.getLogger(__name__).info("start: log=%s models=%s", log_file, f"{base.target(SONNET)} / {base.target(HAIKU)}" if other else "anthropic default")
    for note in startup_notes(base.key_vars() if other else ("ANTHROPIC_API_KEY",)):
        print(note)
    model = RetryingModel(base)  # the one retry policy (ADR 0015), for the Runner, Screening and the Searcher alike
    store = Store(DB_PATH)
    ledger = Ledger(store)
    memory, memory_line = memory_mod.build(root=MEMORY_PATH)
    print(memory_line)
    logging.getLogger(__name__).info(memory_line)
    for folder in (SHOTS_PATH, CAPTURE_PATH):
        if (swept := housekeeping.sweep(folder, housekeeping.retention_days())):
            logging.getLogger(__name__).info("removed %d old item(s) from %s", swept, folder)
    if (cut_off := ledger.close_interrupted()):
        logging.getLogger(__name__).warning("closed %d run(s) the last session left open", cut_off)
    fetcher = Fetcher()
    if web:
        async def forget_chat(chat: str, run_ids: list[str]) -> None:
            await memory.forget_chat(chat)  # what Memory kept from a deleted chat goes with it

        async def remove_capture(chat: str, run_ids: list[str]) -> None:
            capture_mod.Capture(CAPTURE_PATH).remove(run_ids)  # a deleted chat's prompts go with it, whether or not capture is on now

        keeper = ChatKeeper(ledger, SHOTS_PATH, [forget_chat, remove_capture])
        hosts = [h for h in os.environ.get("STEPOUT_REMOTE_HOSTS", "").split(",") if h.strip()]  # set by `stepout remote`
        channel = WebChannel(port=web_port(), shots=SHOTS_PATH, history=StoreHistory(store), keeper=keeper, memory=memory,
                             remote_hosts=hosts, remote_login=os.environ.get("STEPOUT_REMOTE_LOGIN", ""))  # the channel reads history from the app's own Store
        try:
            url = f"http://127.0.0.1:{await channel.start()}"
        except OSError:
            print(f"Port {web_port()} is used by something that is not Stepout. Stop that, or set STEPOUT_PORT to another port.")
            return
        print(f"Stepout web chat: {url}  (Ctrl+C to stop)")
        if hosts:
            remote.keep_awake()
            phone = asyncio.create_task(announce_phone(web_port(), hosts[0], show_qr))  # noqa: F841 (kept: a task nobody refers to can be collected) after the chat is up: its address can only be checked then
        if open_browser:
            webbrowser.open(url)
    else:
        channel = CliChannel()
    intake = Intake(HaikuScreener(model), ledger, lambda conversation_id: history.exchanges(store, conversation_id))
    try:
        files = Files.from_config(GRANTS_PATH)
    except (ValueError, KeyError, OSError) as exc:  # a bad grants.toml must not end the start with a traceback: no folders, and say how to fix it
        print(f"{GRANTS_PATH} could not be read ({exc}), so no folders are allowed until it is fixed. Run `stepout grant` to write it again.")
        files = Files()
    browser = make_browser(channel)
    saved = SavedChannel(channel, ledger)
    def month_left() -> float:
        return month_cap() - ledger.month_spend()

    runner = Runner(model, fetcher, ledger, saved.send, trace=channel.trace, cancel=channel.cancel, files=files, browser=browser, month_left=month_left, memory=memory,
                    capture=capture_mod.from_env(CAPTURE_PATH))
    try:
        learner = Learner(Extractor(model), memory, ledger, trace=channel.trace)
        await run(saved, intake, runner, month_left, memory, learner)
    finally:
        await browser.aclose()


async def announce_phone(port: int, host: str, show_qr: bool) -> None:
    """Repair Serve if it drifted, check the phone address really answers from this laptop, and only then say so (and show the QR)."""
    problem = await asyncio.to_thread(remote.prepare, port, host)
    if problem:
        print(f"Phone access is not working: {problem}\nRun `stepout status` to see which part is off.")
        return
    print(f"From your phone: https://{host}/  (this laptop stays awake while Stepout runs; closing the lid still sleeps it)")
    if show_qr:
        remote.show_qr(f"https://{host}/")


def running_at(port: int) -> str | None:
    """The address of a Stepout already answering on this port, else None (the port is free, or something else holds it)."""
    try:
        code, body = remote.get(f"http://127.0.0.1:{port}/api/health", timeout=2)
    except OSError:
        return None
    return f"http://127.0.0.1:{port}" if code == 200 and '"stepout"' in body else None


def stop() -> None:
    port = web_port()
    pid_file = HOME / f"stepout-{port}.pid"
    if not running_at(port):
        pid_file.unlink(missing_ok=True)  # a crash leaves its file behind
        print("Stepout is not running.")
        return
    try:
        pid = int(pid_file.read_text())
    except (OSError, ValueError):
        print(f"Stepout is running on port {port}, but not started by this version: close its window.")
        return
    # ponytail: a recycled pid is only guarded by the health check above; record the process start time if that ever matters
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    for _ in range(20):
        if not running_at(port):
            break
        time.sleep(0.25)
    pid_file.unlink(missing_ok=True)
    print("Stepout is still running: close its window." if running_at(port) else "Stepout stopped.")


def status() -> bool:
    """`stepout status`: what is set up and what is not, each with its fix. -> True when nothing needs fixing."""
    port = web_port()
    here = running_at(port)
    try:
        grants = init.read_grants(GRANTS_PATH) if GRANTS_PATH.exists() else None
    except (ValueError, KeyError, OSError) as exc:
        grants, unreadable = None, f"The folders file could not be read ({exc}): run `stepout grant` to write it again."
    else:
        unreadable = "The folders question is not answered: run `stepout grant`."
    host = os.environ.get("STEPOUT_REMOTE_HOSTS", "").split(",")[0].strip()
    rows: list[tuple[bool | None, str]] = [
        (bool(here), f"The chat is running at {here}" if here else "The chat is not running: start it with `stepout`."),
        (bool(os.environ.get("ANTHROPIC_API_KEY")), "The API key is set" if os.environ.get("ANTHROPIC_API_KEY") else "No API key: run `stepout init`."),
        (grants is not None, f"{len(grants)} folder(s) allowed (`stepout grant` changes this)" if grants is not None else unreadable),
        *remote.report(port, host),
    ]
    for ok, line in rows:
        print(("ok   " if ok else "--   " if ok is None else "FIX  ") + line)
    return all(ok is not False for ok, _ in rows)


USAGE = """stepout           start the chat and open it in your browser
stepout web       start the chat without opening the browser
stepout cli       chat in this terminal instead
stepout init      set up: your API key, then the folders Stepout may look at
stepout grant     choose which folders Stepout may look at
stepout status    what is set up and what needs fixing, including the phone link
stepout stop      stop the chat that is running
stepout remote    reach this chat from your phone (stepout remote off: stop that)"""


def first_run(ask=input) -> bool:
    """Not set up yet (no key, or the folders question never answered) and someone is at the keyboard: offer `init` once, and the phone
    with it (`stepout remote` later if not now). -> True if the phone was set up just now."""
    other = os.environ.get("STEPOUT_STRONG_MODEL") or os.environ.get("STEPOUT_CHEAP_MODEL")  # another provider's key is set by hand
    if (GRANTS_PATH.exists() and (other or os.environ.get("ANTHROPIC_API_KEY"))) or not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False  # (both: on Windows the null device counts as a terminal)
    if ask("Stepout is not set up yet. Set it up now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        return False
    init.init(ENV_PATH, GRANTS_PATH)
    if os.name == "nt" and ask("Use Stepout from your phone too? [Y/n] ").strip().lower() in ("", "y", "yes"):
        return remote.setup(web_port(), ENV_PATH) is not None
    return False


def serve_web(**options) -> None:
    """The web chat, with a pid file so `stepout stop` finds it (one per port)."""
    pid_file = HOME / f"stepout-{web_port()}.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    try:
        asyncio.run(main(web=True, **options))
    finally:
        pid_file.unlink(missing_ok=True)


def cli(args: Sequence[str] | None = None) -> None:
    """The `stepout` command."""
    args = list(sys.argv[1:] if args is None else args)
    command = args[0] if args else "open"
    load_dotenv(ENV_PATH)  # the key `stepout init` wrote
    if CHECKOUT is not None:
        load_dotenv(CHECKOUT / ".env")  # a source checkout's own .env (development); never the working directory's
    try:
        if command == "init":
            init.init(ENV_PATH, GRANTS_PATH)
        elif command == "grant":
            init.grant(GRANTS_PATH)
        elif command == "remote" and args[1:] == ["off"]:
            remote.off(ENV_PATH)
        elif command == "status":
            sys.exit(0 if status() else 1)
        elif command == "stop":
            stop()
        elif command in ("remote", "open", "web") and (here := running_at(web_port())):
            print(f"Stepout is already running at {here}  (`stepout stop` stops it).")
            if command != "web":
                webbrowser.open(here)
        elif command == "remote":
            if remote.setup(web_port(), ENV_PATH):
                first_run()
                serve_web(open_browser=True, show_qr=True)
        elif command in ("open", "web"):
            serve_web(open_browser=command == "open", show_qr=first_run())
        elif command == "cli":
            first_run()
            asyncio.run(main(web=False))
        else:
            print(USAGE)
    except (KeyboardInterrupt, EOFError):
        print()  # Ctrl+C: stop quietly


if __name__ == "__main__":
    cli(sys.argv[1:] or ["cli"])  # `python -m stepout.app` stays the terminal chat; `python -m stepout.app web` the web one
