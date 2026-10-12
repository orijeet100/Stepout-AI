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
