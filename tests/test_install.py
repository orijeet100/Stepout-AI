"""One command from clone to chat: Home (paths.py), `stepout init` and `stepout grant` (init.py), the `stepout` command."""

import json
import os

import pytest

from stepout import app, init, paths
from stepout.files import Files, blocked_reason, load_grants

windows = pytest.mark.skipif(os.name != "nt", reason="file access is Windows-only")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """init writes what it saves to the environment too: put it back afterwards."""
    for name in ("ANTHROPIC_API_KEY", "STEPOUT_X"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def answers(*replies):
    """An `ask` that gives these replies in order, and records the questions."""
    asked, queue = [], list(replies)

    def ask(question):
        asked.append(question)
        return queue.pop(0)

    ask.asked = asked
    return ask


# ---- Home ------------------------------------------------------------------------------------------------------------


def test_home_is_stepout_home_then_the_checkouts_data_then_the_per_user_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("STEPOUT_HOME", str(tmp_path / "mine"))
    assert paths.home() == (tmp_path / "mine").resolve()
    monkeypatch.delenv("STEPOUT_HOME")
    assert paths.CHECKOUT is not None and paths.home() == paths.CHECKOUT / "data"  # tests run from a checkout: development is unchanged
    monkeypatch.setattr(paths, "CHECKOUT", None)  # an installed copy
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.home() == tmp_path / "local" / "Stepout"


def test_every_data_path_is_under_home():
    for path in (app.ENV_PATH, app.DB_PATH, app.GRANTS_PATH, app.SHOTS_PATH, app.LOGS_PATH, app.MEMORY_PATH, app.CAPTURE_PATH):
        assert path.is_absolute() and app.HOME in path.parents


@windows
def test_the_agents_cannot_reach_home():
    assert blocked_reason(os.path.normcase(str(paths.home() / "memory" / "persona.md")))
    assert blocked_reason(os.path.normcase(str(paths.home())))


def test_off_windows_the_file_hands_fail_closed(monkeypatch, tmp_path):
    (tmp_path / "grants.toml").write_text(f"[[grant]]\npath = {str(tmp_path)!r}\nmode = \"read\"\n")
    monkeypatch.setattr(os, "name", "posix")
    files = Files.from_config(tmp_path / "grants.toml")
    real, why = files._resolve(str(tmp_path))
    assert real is None and "Windows only" in why


# ---- the .env file ---------------------------------------------------------------------------------------------------


def test_set_env_replaces_and_removes_its_line_and_keeps_the_others(tmp_path, monkeypatch):
    env = tmp_path / "home" / ".env"
    monkeypatch.delenv("STEPOUT_X", raising=False)
    env.parent.mkdir()
    env.write_text("OTHER=1\nSTEPOUT_X=old\n")
    init.set_env(env, "STEPOUT_X", "new")
    assert env.read_text().splitlines() == ["OTHER=1", "STEPOUT_X=new"] and os.environ["STEPOUT_X"] == "new"
    init.set_env(env, "STEPOUT_X", "")
    assert env.read_text().splitlines() == ["OTHER=1"] and "STEPOUT_X" not in os.environ


# ---- stepout init ----------------------------------------------------------------------------------------------------


def test_init_keeps_a_good_key_hidden_and_refuses_a_bad_one_writing_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(os, "name", "posix")  # skip the folders part here
    env = tmp_path / ".env"
    secret = answers("sk-bad", "sk-good")
    said = []
    init.init(env, tmp_path / "grants.toml", ask=answers(), secret=secret, out=said.append, check=lambda k: "Anthropic refused that key." if k == "sk-bad" else None)
    assert env.read_text() == "ANTHROPIC_API_KEY=sk-good\n"
    assert "Anthropic refused that key." in said
    assert not any("sk-" in line for line in said) and "sk-" not in capsys.readouterr().out  # never echoed


def test_init_with_a_refused_key_and_then_enter_writes_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    init.init(tmp_path / ".env", tmp_path / "grants.toml", ask=answers(), secret=answers("sk-bad", ""), out=lambda _: None, check=lambda k: "refused")
    assert not (tmp_path / ".env").exists()


def test_init_asks_before_replacing_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-old")
    monkeypatch.setattr(os, "name", "posix")
    ask = answers("")  # Enter: keep it
    init.init(tmp_path / ".env", tmp_path / "grants.toml", ask=ask, secret=answers(), out=lambda _: None, check=lambda k: None)
    assert "Replace it?" in ask.asked[0] and not (tmp_path / ".env").exists()


# ---- stepout grant ---------------------------------------------------------------------------------------------------


def test_grants_round_trip_through_the_files_loader_even_with_quotes_and_backslashes(tmp_path):
    odd = str(tmp_path / "John's \"files\" é")  # a quote cannot be in a Windows name, but the writer must not care
    init.write_grants(tmp_path / "grants.toml", [(odd, "read"), (str(tmp_path), "metadata")])
    assert init.read_grants(tmp_path / "grants.toml") == [(odd, "read"), (str(tmp_path), "metadata")]
    assert [g.mode for g in load_grants(tmp_path / "grants.toml")] == ["read", "metadata"]


@windows
def test_grant_adds_another_folder_with_its_mode_and_removes_one(tmp_path, monkeypatch):
    monkeypatch.setattr(init, "_usual_folders", lambda: [])
    work, old = tmp_path / "Work", tmp_path / "Old"
    work.mkdir(), old.mkdir()
    grants = tmp_path / "config" / "grants.toml"
    init.write_grants(grants, [(str(old), "metadata")])
    said = []
    init.grant(grants, ask=answers("1", "1", str(tmp_path / "nope"), str(work), "2"), out=said.append)  # remove Old; "another folder"; a typo; Work; read
    assert init.read_grants(grants) == [(os.path.realpath(work), "read")]
    assert any("not a folder" in line for line in said)


@windows
def test_grant_refuses_off_limits_and_odd_paths(tmp_path):
    assert init.checked_folder(r"C:\Windows")[0] is None
    assert init.checked_folder(r"\\server\share")[0] is None
    assert init.checked_folder("relative\\path")[0] is None
    assert init.checked_folder(str(paths.home()))[0] is None  # Stepout's own folder
    assert init.checked_folder(str(tmp_path))[0] == os.path.realpath(tmp_path)


@windows
def test_a_whole_drive_needs_its_name_typed_otherwise_its_folders_are_ticked(tmp_path, monkeypatch):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
    picked = init._pick_inside(str(tmp_path), answers("2"), lambda _: None)
    assert picked == [str(tmp_path / "b")]
    assert init._pick_inside(str(tmp_path), answers(tmp_path.name), lambda _: None) == [str(tmp_path)]


@windows
def test_answering_no_folders_still_writes_the_file_so_it_is_not_asked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(init, "_usual_folders", lambda: [])
    init.grant(tmp_path / "grants.toml", ask=answers(""), out=lambda _: None)
    assert (tmp_path / "grants.toml").exists() and init.read_grants(tmp_path / "grants.toml") == []


# ---- the stepout command ---------------------------------------------------------------------------------------------


def test_an_unknown_command_prints_the_usage(capsys):
    app.cli(["--help"])
    assert "stepout remote" in capsys.readouterr().out


def test_first_run_does_not_ask_when_no_one_is_at_the_keyboard(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    app.first_run(ask=answers())  # would raise if it asked


def test_first_run_offers_setup_when_the_folders_question_was_never_answered(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    tty = type("Tty", (), {"isatty": lambda self: True, "write": lambda self, text: len(text), "flush": lambda self: None})()
    monkeypatch.setattr("sys.stdin", tty)
    monkeypatch.setattr("sys.stdout", tty)
    ask = answers("n")
    app.first_run(ask=ask)
    assert "not set up yet" in ask.asked[0]
    (tmp_path / "grants.toml").write_text("")
    app.first_run(ask=answers())  # set up: no question


def a_terminal(monkeypatch):
    tty = type("Tty", (), {"isatty": lambda self: True, "write": lambda self, text: len(text), "flush": lambda self: None})()
    monkeypatch.setattr("sys.stdin", tty)
    monkeypatch.setattr("sys.stdout", tty)


@windows
def test_first_run_offers_the_phone_in_the_same_flow_and_returns_whether_it_was_set_up(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.setattr(app, "ENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a_terminal(monkeypatch)
    calls = []
    monkeypatch.setattr(app.init, "init", lambda env, grants, **kw: calls.append("init"))
    monkeypatch.setattr(app.remote, "setup", lambda port, env, **kw: calls.append("remote") or "https://x/")
    assert app.first_run(ask=answers("", "y")) is True and calls == ["init", "remote"]  # Enter = yes, then yes to the phone
    calls.clear()
    assert app.first_run(ask=answers("y", "n")) is False and calls == ["init"]  # no to the phone: `stepout remote` later
    calls.clear()
    assert app.first_run(ask=answers("n")) is False and calls == []  # no to setup: nothing else is asked


async def test_the_health_route_says_what_is_answering(tmp_path):
    import aiohttp

    from stepout.channels.web import WebChannel
    from tests.test_web_channel import FixtureHistory

    channel = WebChannel(port=0, shots=tmp_path, history=FixtureHistory())
    port = await channel.start()
    try:
        import asyncio

        assert await asyncio.to_thread(app.running_at, port) == f"http://127.0.0.1:{port}"
        async with aiohttp.ClientSession() as session:
            assert await (await session.get(f"http://127.0.0.1:{port}/api/health")).json() == {"app": "stepout", "v": 1}
            assert (await session.get(f"http://127.0.0.1:{port}/api/health", headers={"Host": "evil.example"})).status == 403  # the guard covers it too
    finally:
        await channel.stop()
    assert app.running_at(port) is None  # nothing there any more


def test_something_else_on_the_port_is_not_taken_for_stepout():
    import http.server
    import threading

    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert app.running_at(server.server_address[1]) is None
    finally:
        server.shutdown()


def test_stop_with_nothing_running_says_so_and_clears_a_stale_pid_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setenv("STEPOUT_PORT", "1")  # nothing listens here
    (tmp_path / "stepout-1.pid").write_text("999999")
    app.stop()
    assert "not running" in capsys.readouterr().out and not (tmp_path / "stepout-1.pid").exists()


def test_stop_ends_the_process_named_in_the_pid_file_and_only_when_stepout_answers(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setenv("STEPOUT_PORT", "8123")
    (tmp_path / "stepout-8123.pid").write_text("4242")
    alive, killed = [True], []
    monkeypatch.setattr(app, "running_at", lambda port: "http://127.0.0.1:8123" if alive[0] else None)
    monkeypatch.setattr(app.subprocess, "run", lambda argv, **kw: killed.append(argv) or alive.__setitem__(0, False))
    app.stop()
    assert killed == [["taskkill", "/PID", "4242", "/T", "/F"]] and "stopped" in capsys.readouterr().out
    assert not (tmp_path / "stepout-8123.pid").exists()


def test_stop_without_a_pid_file_does_not_guess(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "HOME", tmp_path)
    monkeypatch.setenv("STEPOUT_PORT", "8124")
    monkeypatch.setattr(app, "running_at", lambda port: "http://127.0.0.1:8124")
    killed = []
    monkeypatch.setattr(app.subprocess, "run", lambda *a, **kw: killed.append(a))
    app.stop()
    assert killed == [] and "close its window" in capsys.readouterr().out


def test_status_lists_each_part_and_fails_when_one_needs_fixing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(app, "GRANTS_PATH", tmp_path / "grants.toml")
    monkeypatch.setenv("STEPOUT_PORT", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("STEPOUT_REMOTE_HOSTS", "")
    assert app.status() is False
    out = capsys.readouterr().out
    assert "FIX  The chat is not running" in out and "FIX  No API key" in out and "FIX  The folders question" in out
    assert "--   Phone access is not set up" in out  # information, not a fault
    monkeypatch.setattr(app, "running_at", lambda port: "http://127.0.0.1:1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    (tmp_path / "grants.toml").write_text("")
    assert app.status() is True


def test_remote_while_the_chat_runs_sets_the_phone_up_and_says_to_restart_it(monkeypatch, capsys):
    monkeypatch.setattr(app, "running_at", lambda port: f"http://127.0.0.1:{port}")
    started, opened = [], []
    monkeypatch.setattr(app.remote, "setup", lambda port, env, **kw: "https://x.ts.net/")
    monkeypatch.setattr(app, "serve_web", lambda **kw: started.append(kw))
    monkeypatch.setattr(app.webbrowser, "open", opened.append)
    app.cli(["remote"])
    out = capsys.readouterr().out
    assert started == [] and opened == []  # no second copy, no second page
    assert "started without it" in out and "stepout stop" in out
    monkeypatch.setattr(app.remote, "setup", lambda port, env, **kw: None)  # setup failed or was declined: nothing more is said
    app.cli(["remote"])
    assert "started without it" not in capsys.readouterr().out


def test_remote_with_nothing_running_sets_up_then_starts_with_the_qr(monkeypatch):
    monkeypatch.setattr(app, "running_at", lambda port: None)
    started = []
    monkeypatch.setattr(app.remote, "setup", lambda port, env, **kw: "https://x.ts.net/")
    monkeypatch.setattr(app, "first_run", lambda *a, **kw: False)
    monkeypatch.setattr(app, "serve_web", lambda **kw: started.append(kw))
    app.cli(["remote"])
    assert started == [{"open_browser": True, "show_qr": True}]


def test_a_second_start_opens_the_running_one_instead_of_starting_again(monkeypatch, capsys):
    monkeypatch.setattr(app, "running_at", lambda port: f"http://127.0.0.1:{port}")
    opened, started = [], []
    monkeypatch.setattr(app.webbrowser, "open", opened.append)
    monkeypatch.setattr(app, "serve_web", lambda **kw: started.append(kw))
    app.cli(["open"])
    assert opened and started == [] and "already running" in capsys.readouterr().out
    opened.clear()
    app.cli(["web"])
    assert opened == [] and started == []  # `web` is the no-browser form


# ---- a grants.toml that a text editor touched (found in the clean-room run: PowerShell's Set-Content wrote a BOM and the app died) -----------


def test_a_grants_file_with_a_byte_order_mark_still_loads(tmp_path):
    folder = tmp_path / "Work"
    folder.mkdir()
    path = tmp_path / "grants.toml"
    path.write_bytes(b"\xef\xbb\xbf" + f'[[grant]]\npath = {json.dumps(str(folder))}\nmode = "read"\n'.encode())
    assert [g.mode for g in load_grants(path)] == ["read"] and init.read_grants(path) == [(str(folder), "read")]


def test_an_unreadable_grants_file_does_not_end_the_start_it_allows_nothing_and_says_how_to_fix_it(monkeypatch, tmp_path, capsys):
    path = tmp_path / "grants.toml"
    path.write_text("this is = = not toml\n")
    with pytest.raises(ValueError):
        load_grants(path)  # the loader is strict; the start-up catches it
    monkeypatch.setattr(app, "GRANTS_PATH", path)
    monkeypatch.setenv("STEPOUT_PORT", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert app.status() is False
    assert "could not be read" in capsys.readouterr().out  # `stepout status` says so rather than crashing


@windows
def test_grant_repairs_an_unreadable_file(tmp_path, monkeypatch):
    monkeypatch.setattr(init, "_usual_folders", lambda: [])
    path = tmp_path / "grants.toml"
    path.write_text("[[grant\n")
    said = []
    init.grant(path, ask=answers(""), out=said.append)
    assert any("could not be read" in s for s in said) and init.read_grants(path) == []


# ---- where the data lives is said the same way everywhere (found by the docs audit) ---------------------------------------------------------


def test_the_unexpected_failure_line_names_the_real_log_file():
    from stepout import logs
    from stepout.failure import UNEXPECTED

    assert str(app.LOGS_PATH / logs.LOG_NAME) in UNEXPECTED  # not a "data/logs" that is only true in a checkout


def test_defaults_that_were_relative_to_the_working_folder_now_follow_home(monkeypatch, tmp_path):
    from stepout import memory as memory_mod
    from stepout.channels.web import WebChannel
    from tests.test_web_channel import FixtureHistory

    monkeypatch.setenv("STEPOUT_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path / "..")  # somewhere that is not Home
    _, line = memory_mod.build({"STEPOUT_MEMORY": "files"})
    assert str(tmp_path / "memory") in line  # "Memory: plain files in <Home>\memory."
    assert WebChannel(port=0, history=FixtureHistory())._shots == tmp_path / "runs"
