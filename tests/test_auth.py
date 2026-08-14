import auth


def test_verify_password_correct(monkeypatch):
    monkeypatch.setenv("RECRUITER_PASSWORD", "correct-horse")
    assert auth.verify_password("recruiter", "correct-horse") is True


def test_verify_password_incorrect(monkeypatch):
    monkeypatch.setenv("RECRUITER_PASSWORD", "correct-horse")
    assert auth.verify_password("recruiter", "wrong") is False


def test_verify_password_missing_env(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert auth.verify_password("admin", "anything") is False


def test_login_success_returns_working_token(monkeypatch):
    monkeypatch.setenv("RECRUITER_PASSWORD", "pw123")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    token = auth.login("Jane", "recruiter", "pw123")
    assert token is not None
    session = auth.read_session_token(token)
    assert session == {"name": "Jane", "role": "recruiter"}


def test_login_wrong_password_returns_none(monkeypatch):
    monkeypatch.setenv("RECRUITER_PASSWORD", "pw123")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    assert auth.login("Jane", "recruiter", "wrong") is None


def test_login_invalid_role_returns_none(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    assert auth.login("Jane", "superadmin", "whatever") is None


def test_read_session_token_rejects_garbage(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    assert auth.read_session_token("not-a-real-token") is None
