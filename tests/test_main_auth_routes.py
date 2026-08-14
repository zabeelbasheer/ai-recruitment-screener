from fastapi.testclient import TestClient

import main


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("RECRUITER_PASSWORD", "recruit-pw")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setattr(main.db, "DB_PATH", tmp_path / "test.db")
    main.db.init_db()
    return TestClient(main.app)


def test_login_success(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/login", json={"name": "Jane", "role": "recruiter", "password": "recruit-pw"}
    )
    assert response.status_code == 200
    assert response.json() == {"name": "Jane", "role": "recruiter"}
    assert "session" in response.cookies


def test_login_wrong_password(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/login", json={"name": "Jane", "role": "recruiter", "password": "nope"}
    )
    assert response.status_code == 401


def test_session_requires_login(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.get("/session")
    assert response.status_code == 401


def test_session_after_login(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    client.post(
        "/login", json={"name": "Jane", "role": "recruiter", "password": "recruit-pw"}
    )
    response = client.get("/session")
    assert response.status_code == 200
    assert response.json()["name"] == "Jane"


def test_logout_clears_session(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    client.post(
        "/login", json={"name": "Jane", "role": "recruiter", "password": "recruit-pw"}
    )
    client.post("/logout")
    response = client.get("/session")
    assert response.status_code == 401
