---
date: 2026-10-07
kind: change
lane: main
status: accepted
title: B1a isolation guards
tags: [worktrees, ownership]
refs: [docs/plan/main-worktree.md, src/stepout/app.py, pyproject.toml, tests/test_isolation.py, scripts/owners.py, tests/test_owners.py]
---

**What.** (1) `app.py` reads `STEPOUT_PORT` (default 8765) through `web_port()` and passes it to `WebChannel`. (2) pytest gets `pythonpath = ["src", "."]` and `testpaths = ["tests"]`: tests import the `src` of the checkout they sit in, whatever editable install the venv holds, and the UI lane's `web/e2e` tests never join a Python run. (3) `tests/test_isolation.py`: `stepout` must be imported from `<repo>/src` of the checkout that contains `tests/`. (4) `scripts/owners.py --lane main|ui <branch>`: the ownership table of `docs/plan/README.md` as code; exit 1 and a list of paths if the branch (against `main`, three-dot, renames counted as delete plus add) changed a path its lane does not own. The merge agent runs it once per lane.

**Why.** Two worktrees must run side by side, and a worktree whose venv's editable install points at another checkout would test the wrong code and still pass. The ownership rule is only worth having if it is checked at every merge.

**Alternatives.** Isolation test comparing against the repo root instead of `<root>/src`: a worktree sits *inside* the primary checkout, so "under the primary root" is true of both and the check would pass wrongly. Parsing the table out of the README instead of keeping it in code: brittle, and the table has prose in it.

**Evidence.** Offline suite 142 passed, 6 deselected (135 before, plus 2 isolation and 5 owners tests). By hand: the primary checkout's venv run against this worktree's tests with `-o pythonpath=.` fails `test_stepout_is_imported_from_this_checkout` ("imported stepout from D:\Stepout AI\src\… (another checkout's venv?)"); with the committed config it passes. Two backends started side by side on 8791 and 8792, each in its own working directory, both answered HTTP; a third start on 8791 was refused. `owners.py` rejects a UI-lane change to `src/stepout/runner.py` and a Main-lane change to `web/src/App.tsx` (`tests/test_owners.py`, which also drives it through a throwaway git repo). Files: `src/stepout/app.py`, `pyproject.toml`, `scripts/owners.py`, `tests/test_isolation.py`, `tests/test_owners.py`. Commit: see the branch.
