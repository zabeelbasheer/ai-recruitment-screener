import io
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
import requirements_extractor
import scorer


def _fake_requirements_llm():
    content = (
        '{"required_certifications": [], '
        '"min_years_experience": 0, '
        '"required_keywords": []}'
    )
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def _fake_scoring_llm():
    content = '{"score": 4, "rationale": "Solid match on paper."}'
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def _client(monkeypatch, tmp_path, name="Jane", role="recruiter"):
    monkeypatch.setenv("RECRUITER_PASSWORD", "recruit-pw")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setattr(main.db, "DB_PATH", tmp_path / "test.db")
    main.db.init_db()
    monkeypatch.setattr(requirements_extractor, "get_llm", _fake_requirements_llm)
    monkeypatch.setattr(scorer, "get_llm", _fake_scoring_llm)
    client = TestClient(main.app)
    password = "recruit-pw" if role == "recruiter" else "admin-pw"
    client.post("/login", json={"name": name, "role": role, "password": password})
    return client


def test_screen_single_returns_scorecard(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    resume_file = io.BytesIO(b"Name: Jane Doe\n5 years of relevant experience.")
    response = client.post(
        "/screen/single",
        data={"jd_text": "Looking for a coder."},
        files={"resume": ("jane.txt", resume_file, "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["candidate_name"] == "Jane Doe"
    assert body["result"]["hard_filter_passed"] is True


def test_screen_batch_ranks_candidates(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    files = [
        ("resumes", ("a.txt", io.BytesIO(b"Name: Candidate A\n1 years of relevant experience."), "text/plain")),
        ("resumes", ("b.txt", io.BytesIO(b"Name: Candidate B\n10 years of relevant experience."), "text/plain")),
    ]
    response = client.post("/screen/batch", data={"jd_text": "Looking for a coder."}, files=files)
    assert response.status_code == 200
    assert len(response.json()["result"]["candidates"]) == 2


def test_export_csv_rejects_single_run(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    resume_file = io.BytesIO(b"Name: Jane Doe\n5 years of relevant experience.")
    single_response = client.post(
        "/screen/single",
        data={"jd_text": "Looking for a coder."},
        files={"resume": ("jane.txt", resume_file, "text/plain")},
    )
    run_id = single_response.json()["run_id"]
    response = client.get(f"/export/csv/{run_id}")
    assert response.status_code == 400


def test_export_csv_returns_csv_for_batch_run(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    files = [
        ("resumes", ("a.txt", io.BytesIO(b"Name: Candidate A\n1 years of relevant experience."), "text/plain")),
    ]
    batch_response = client.post("/screen/batch", data={"jd_text": "Looking for a coder."}, files=files)
    run_id = batch_response.json()["run_id"]
    response = client.get(f"/export/csv/{run_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_runs_recruiter_only_sees_own(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, name="Jane")
    resume_file = io.BytesIO(b"Name: Jane Doe\n5 years of relevant experience.")
    client.post(
        "/screen/single",
        data={"jd_text": "Looking for a coder."},
        files={"resume": ("jane.txt", resume_file, "text/plain")},
    )
    response = client.get("/runs")
    assert response.status_code == 200
    assert all(r["username"] == "Jane" for r in response.json())


def test_runs_admin_sees_all(monkeypatch, tmp_path):
    monkeypatch.setenv("RECRUITER_PASSWORD", "recruit-pw")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setattr(main.db, "DB_PATH", tmp_path / "test.db")
    main.db.init_db()
    monkeypatch.setattr(requirements_extractor, "get_llm", _fake_requirements_llm)
    monkeypatch.setattr(scorer, "get_llm", _fake_scoring_llm)

    recruiter_client = TestClient(main.app)
    recruiter_client.post("/login", json={"name": "Jane", "role": "recruiter", "password": "recruit-pw"})
    resume_file = io.BytesIO(b"Name: Jane Doe\n5 years of relevant experience.")
    recruiter_client.post(
        "/screen/single",
        data={"jd_text": "Looking for a coder."},
        files={"resume": ("jane.txt", resume_file, "text/plain")},
    )

    admin_client = TestClient(main.app)
    admin_client.post("/login", json={"name": "Amir", "role": "admin", "password": "admin-pw"})
    response = admin_client.get("/runs")
    assert response.status_code == 200
    assert any(r["username"] == "Jane" for r in response.json())
