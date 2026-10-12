import pytest

import sqlite3

from stepout.domain import Event
from stepout.ledger import Ledger
from stepout.store import Store


def test_role_and_parent_are_recorded(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    parent = Event(kind="step", role="orchestrator", task_id="t", data={})
    child = Event(kind="step", role="web_research", parent=parent.id, task_id="t", data={"x": 1}, cost_usd=0.01)
    ledger.record(parent)
    ledger.record(child)
    back = {e.id: e for e in ledger.query("t")}
    assert back[child.id].role == "web_research"
    assert back[child.id].parent == parent.id
    assert back[parent.id].parent is None


def test_reopening_a_database_does_not_rerun_migrations(tmp_path):
    Store(tmp_path / "t.db").close()
    Store(tmp_path / "t.db").close()  # a second ALTER TABLE would raise "duplicate column name"


def test_an_existing_v1_database_is_upgraded(tmp_path):
    # A database created before migration 0002 (what data/stepout.db looks like today).
    path = tmp_path / "old.db"
    from stepout.store import _MIGRATIONS_DIR

    conn = sqlite3.connect(path)
    conn.executescript((_MIGRATIONS_DIR / "0001_init.sql").read_text())
    conn.commit()
    conn.close()
    ledger = Ledger(Store(path))
    ledger.record(Event(kind="step", role="web_research", data={}))
    assert ledger.query()[0].role == "web_research"


def test_a_run_ends_with_its_totals_and_an_old_style_call_still_works(tmp_path):
    from stepout.domain import Outcome, Task

    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    for run_id in ("r1", "r2"):
        ledger.start_run(Task(user_id="u", request="q", conversation_id="c"), run_id, 1.0)
    ledger.end_run("r1", Outcome.DONE, 0.02, "", input_tokens=1200, output_tokens=90, retries=2, retry_wait_s=3.5)
    ledger.end_run("r2", Outcome.DONE, 0.01, "")  # the four-argument call every older caller makes
    one, two = (store.query("SELECT input_tokens, output_tokens, retries, retry_wait_s FROM runs WHERE id = ?", (r,))[0] for r in ("r1", "r2"))
    assert tuple(one) == (1200, 90, 2, 3.5) and tuple(two) == (0, 0, 0, 0.0)


def test_a_run_the_app_left_open_is_closed_as_interrupted_once_with_a_line(tmp_path):
    from stepout.domain import Outcome, Task

    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    ledger.start_run(Task(user_id="u", request="cut off", conversation_id="c1"), "open", 1.0)
    ledger.start_run(Task(user_id="u", request="finished", conversation_id="c2"), "done", 1.0)
    ledger.end_run("done", Outcome.DONE, 0.01, "")

    assert ledger.close_interrupted() == 1 and ledger.close_interrupted() == 0
    rows = {r["id"]: r for r in store.query("SELECT id, outcome, ended_at FROM runs")}
    assert rows["open"]["outcome"] == "interrupted" and rows["open"]["ended_at"] and rows["done"]["outcome"] == "done"
    (line,) = [e for e in ledger.query() if e.kind == "error"]
    assert (line.run_id, line.conversation_id, line.data["cause"]) == ("open", "c1", "interrupted")


def test_a_database_with_data_is_copied_before_a_migration_changes_it(tmp_path):
    from stepout.store import _MIGRATIONS_DIR

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript((_MIGRATIONS_DIR / "0001_init.sql").read_text())
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    Store(path).close()
    assert (tmp_path / "old.db.bak-before-v2").exists()  # named for the first version it lacked
    Store(path).close()  # nothing pending now: no second copy, and no new file
    assert sorted(p.name for p in tmp_path.iterdir()) == ["old.db", "old.db.bak-before-v2"]


def test_a_new_database_is_not_copied(tmp_path):
    Store(tmp_path / "new.db").close()
    assert [p.name for p in tmp_path.iterdir()] == ["new.db"]


def test_the_months_spend_counts_runs_and_messages_that_never_became_runs_once(tmp_path):
    from datetime import datetime, timezone

    from stepout.domain import Outcome, Task

    store = Store(tmp_path / "t.db")
    ledger = Ledger(store)
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)

    def run(run_id, cost, when):
        ledger.start_run(Task(user_id="u", request="q", conversation_id="c"), run_id, 1.0)
        ledger.end_run(run_id, Outcome.DONE, cost, "")
        store.execute("UPDATE runs SET started_at = ? WHERE id = ?", (when.isoformat(), run_id))

    run("this-month", 0.30, datetime(2026, 10, 2, tzinfo=timezone.utc))
    run("last-month", 0.50, datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc))
    run("next-month", 0.70, datetime(2026, 11, 1, tzinfo=timezone.utc))

    def event(kind, cost, data, when=datetime(2026, 10, 3, tzinfo=timezone.utc)):
        ledger.record(Event(kind=kind, conversation_id="c", data=data, cost_usd=cost, at=when))

    event("screening", 0.01, {"decision": "decline"})  # a message that cost money and did not become a Run
    event("screening", 0.02, {"decision": "chat"})
    event("screening", 0.04, {"decision": "proceed"})  # its cost is in the Run's total already
    event("screening_fallback", 0.04, {})
    event("screening", 0.08, {"decision": "decline"}, when=datetime(2026, 9, 3, tzinfo=timezone.utc))  # last month

    assert ledger.month_spend(now) == pytest.approx(0.30 + 0.01 + 0.02)
    assert ledger.month_spend(datetime(2026, 12, 20, tzinfo=timezone.utc)) == 0.0
