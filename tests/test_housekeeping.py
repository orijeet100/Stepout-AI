import os
import time

from stepout import housekeeping


def age(path, days, now):
    stamp = now - days * 86_400
    os.utime(path, (stamp, stamp))


def test_what_is_older_than_the_limit_goes_and_the_rest_stays(tmp_path):
    now = time.time()
    old_run, new_run, old_file = tmp_path / "run-old", tmp_path / "run-new", tmp_path / "old.jsonl"
    old_run.mkdir()
    (old_run / "1.jpg").write_bytes(b"x")
    new_run.mkdir()
    old_file.write_text("x")
    age(old_run, 40, now)
    age(old_file, 31, now)
    age(new_run, 2, now)

    assert housekeeping.sweep(tmp_path, 30, now=now) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run-new"]


def test_a_missing_folder_is_not_an_error(tmp_path):
    assert housekeeping.sweep(tmp_path / "nope", 30) == 0


def test_the_limit_comes_from_the_environment_with_a_default():
    assert housekeeping.retention_days({}) == 30
    assert housekeeping.retention_days({"STEPOUT_RETENTION_DAYS": "7"}) == 7
    assert housekeeping.retention_days({"STEPOUT_RETENTION_DAYS": "soon"}) == 30
    assert housekeeping.retention_days({"STEPOUT_RETENTION_DAYS": "0"}) == 30
