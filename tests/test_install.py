"""One command from clone to chat: Home (paths.py), `stepout init` and `stepout grant` (init.py), the `stepout` command."""

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
