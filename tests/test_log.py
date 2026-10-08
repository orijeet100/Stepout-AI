"""The decision/change log tool: the check that keeps docs honest, and the query that makes the log useful."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("log", Path(__file__).resolve().parents[1] / "scripts" / "log.py")
log = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log)


def test_code_without_an_entry_fails_the_check():
    assert log.needs_entry(["src/stepout/runner.py"])
    assert log.needs_entry(["web/src/App.tsx", "docs/STATUS.md"])
    assert log.needs_entry(["src\\stepout\\migrations\\0002_x.sql"])  # Windows separators
    assert log.needs_entry(["docs/log/README.md", "src/stepout/runner.py"])  # the README is not an entry


def test_code_with_an_entry_or_docs_only_passes():
    assert not log.needs_entry(["src/stepout/runner.py", "docs/log/2026-10-07-x.md"])
    assert not log.needs_entry(["docs/STATUS.md", "src/stepout/CONTEXT.md", "tests/test_gate.py"])


def test_new_then_list_roundtrip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(log, "LOG", tmp_path)
    assert log.main(["new", "--kind", "decision", "--lane", "ui", "--title", "Big viewer opens on click", "--tags", "viewer,ui"]) == 0
    assert log.main(["new", "--kind", "change", "--lane", "main", "--title", "Persist conversations"]) == 0
    capsys.readouterr()
    log.main(["list", "--lane", "ui"])
    out = capsys.readouterr().out
    assert "Big viewer opens on click" in out and "Persist conversations" not in out
    log.main(["list", "--tag", "viewer"])
    assert "Big viewer opens on click" in capsys.readouterr().out
