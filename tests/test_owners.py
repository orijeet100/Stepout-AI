"""The ownership check: a lane that touches the other lane's files fails the merge."""

import importlib.util
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location("owners", Path(__file__).resolve().parents[1] / "scripts" / "owners.py")
owners = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owners)


def test_ui_lane_may_not_touch_the_backend():
    assert owners.violations("ui", ["web/src/App.tsx", "src/stepout/runner.py"]) == ["src/stepout/runner.py"]
    assert owners.violations("ui", ["tests/test_gate.py", "pyproject.toml", "docs/plan/main-worktree.md"]) != []


def test_main_lane_may_not_touch_the_page():
    assert owners.violations("main", ["src/stepout/runner.py", "web/src/App.tsx"]) == ["web/src/App.tsx"]
    assert owners.violations("main", ["src/stepout/channels/web.py", "docs/plan/ui-worktree.md"]) != []


def test_each_lane_may_touch_its_own_files_and_the_shared_ones():
    shared = ["docs/ui-contract.md", "docs/log/2026-10-07-x.md", "docs/STATUS.md"]
    assert owners.violations("ui", ["web/fixtures/a.json", "src/stepout/channels/web.py", "docs/plan/ui-worktree.md", *shared]) == []
    assert owners.violations("main", ["src/stepout/runner.py", "tests/test_gate.py", "scripts/owners.py", ".githooks/pre-commit", *shared]) == []


def test_windows_separators_are_normalised():
    assert owners.violations("main", ["web\\src\\App.tsx"]) == ["web\\src\\App.tsx"]


def test_main_reads_the_branch_diff_from_git(tmp_path, monkeypatch, capsys):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-b", "main")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "App.tsx").write_text("a")
    git("add", "."), git("commit", "-m", "base")
    git("switch", "-c", "lane")
    (tmp_path / "web" / "App.tsx").write_text("b")
    git("commit", "-am", "touch the page")
    monkeypatch.setattr(owners, "ROOT", tmp_path)
    assert owners.main(["--lane", "ui", "lane"]) == 0
    assert owners.main(["--lane", "main", "lane"]) == 1
    assert "web/App.tsx" in capsys.readouterr().err
