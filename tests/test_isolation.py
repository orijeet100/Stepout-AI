"""Two checkouts side by side: tests must run this checkout's code, and the port must be settable."""

from pathlib import Path

import stepout

ROOT = Path(__file__).resolve().parents[1]


def test_stepout_is_imported_from_this_checkout():
    # Compare with ROOT/src, not ROOT: a worktree lives *inside* the primary checkout, so "under the primary root" is true of both.
    where = Path(stepout.__file__).resolve()
    assert where.is_relative_to(ROOT / "src"), f"tests in {ROOT} imported stepout from {where} (another checkout's venv?)"


def test_port_defaults_to_8765_and_follows_stepout_port(monkeypatch):
    from stepout.app import web_port  # here, so a wrong-checkout import fails the test above first, with its clear message

    monkeypatch.delenv("STEPOUT_PORT", raising=False)
    assert web_port() == 8765
    monkeypatch.setenv("STEPOUT_PORT", "8780")
    assert web_port() == 8780
