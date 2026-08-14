import db


def test_init_db_creates_table(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    assert path.exists()


def test_save_and_get_run(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    run_id = db.save_run("jane", "recruiter", "JD text", "single", {"fit_pct": 80}, db_path=path)
    runs = db.get_runs(username="jane", db_path=path)
    assert len(runs) == 1
    assert runs[0]["result"]["fit_pct"] == 80
    assert runs[0]["id"] == run_id


def test_get_runs_filters_by_username(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    db.save_run("jane", "recruiter", "JD 1", "single", {}, db_path=path)
    db.save_run("bob", "recruiter", "JD 2", "single", {}, db_path=path)
    jane_runs = db.get_runs(username="jane", db_path=path)
    assert len(jane_runs) == 1
    assert jane_runs[0]["username"] == "jane"


def test_get_runs_no_filter_returns_all(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    db.save_run("jane", "recruiter", "JD 1", "single", {}, db_path=path)
    db.save_run("bob", "recruiter", "JD 2", "single", {}, db_path=path)
    all_runs = db.get_runs(db_path=path)
    assert len(all_runs) == 2


def test_get_run_by_id(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    run_id = db.save_run("jane", "recruiter", "JD 1", "batch", {"candidates": []}, db_path=path)
    run = db.get_run(run_id, db_path=path)
    assert run["mode"] == "batch"


def test_get_run_missing_returns_none(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    assert db.get_run(999, db_path=path) is None
