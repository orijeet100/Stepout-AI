import sqlite3

from stepout.domain import Event
from stepout.ledger import Ledger
from stepout.store import Store


def test_role_and_parent_are_recorded(tmp_path):
    ledger = Ledger(Store(tmp_path / "t.db"))
    parent = Event(kind="step", role="orchestrator", task_id="t", data={})
    child = Event(kind="step", role="direct", parent=parent.id, task_id="t", data={"x": 1}, cost_usd=0.01)
    ledger.record(parent)
    ledger.record(child)
    back = {e.id: e for e in ledger.query("t")}
    assert back[child.id].role == "direct"
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
    ledger.record(Event(kind="step", role="direct", data={}))
    assert ledger.query()[0].role == "direct"
