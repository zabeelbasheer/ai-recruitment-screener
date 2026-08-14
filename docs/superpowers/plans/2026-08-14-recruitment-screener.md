# AI Recruitment Screener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-tier AI recruitment screener — FastAPI + vanilla JS app that scores healthcare BPO resumes against a job description using deterministic hard filters plus LLM soft-scoring, with role-based auth, run history, CSV export, and a heuristic fairness check.

**Architecture:** Single-resume scoring (`pipeline.screen_resume`) is the core function: parse resume → deterministic hard filters (Python) → LLM soft-scoring rubric (LangChain + Groq, `PydanticOutputParser`) → aggregate to a fit %. Batch mode loops this function and adds ranking + a fairness proxy check. FastAPI serves both the JSON API and a single static `index.html` (vanilla JS/CSS) frontend, gated by role-based session-cookie auth (Recruiter/Admin) backed by SQLite run history.

**Tech Stack:** Python 3.11, `uv`, FastAPI + Uvicorn, vanilla JS/HTML/CSS, LangChain (`langchain-core`, `langchain-groq`) for `PydanticOutputParser` + prompt templates, Groq `llama-3.3-70b-versatile`, `pdfplumber`, `pandas`, `bcrypt`, `itsdangerous`, SQLite, `python-dotenv`.

**Spec:** `docs/superpowers/specs/2026-08-14-recruitment-resume-ai-design.md`

## Global Constraints

- Python 3.11, dependency management via `uv` only (no pip/poetry).
- Backend is FastAPI + Uvicorn. Frontend is a single `static/index.html` + `static/style.css` + `static/app.js` — **no Streamlit**.
- LangChain is used only for `PydanticOutputParser` + prompt templates on the two LLM call sites (requirement extraction, criterion scoring) — not wrapped around code that doesn't need it.
- LLM: Groq `llama-3.3-70b-versatile` via `langchain-groq`'s `ChatGroq`, model name overridable via `MODEL_NAME` env var.
- Hard filters (license/cert presence, min years, required keywords) are pure deterministic Python — never an LLM judgment call on pass/fail.
- Every LLM-scored criterion always returns a rationale — not a toggle, part of the data contract.
- Auth: two fixed roles, Recruiter and Admin, via `RECRUITER_PASSWORD` / `ADMIN_PASSWORD` env vars (bcrypt-compared), signed session cookie (`itsdangerous`), no self-registration.
- Persistence: SQLite (`data/screening.db`), stores screening runs scoped by submitting user; Admin sees all runs, Recruiter sees only their own.
- Repo stays `ai-recruitment-screener` (existing folder/GitHub remote reused, not renamed).
- Disclaimer banner text (verbatim, persistent in the UI): "Synthetic demo data only — not used for real hiring decisions. No real candidate or client information."
- Branding: "Zeta Health AI" header, tagline "Clinical operations, intelligently governed.", About + Tags footer matching `hr-policy-bot` and `ai-governance-audit-tool`.
- No live-LLM calls in automated tests — all LLM call sites accept an injectable `llm` parameter for test doubles; the default (`get_llm()`) is only exercised manually.
- Sample data resumes must follow the exact phrasing conventions defined in Task 15 so the deterministic parser (Task 5) can extract structured fields from hand-written text.

## File Structure

```
ai-recruitment-screener/
├── main.py                      # FastAPI app: auth routes, screening routes, static mount
├── auth.py                      # bcrypt password check, session token sign/verify
├── db.py                        # SQLite schema + CRUD for screening runs
├── resume_parser.py             # PDF/text extraction + heuristic structured fields
├── requirements_extractor.py    # Step A: JD -> structured hard requirements (LLM)
├── hard_filters.py              # Step B: deterministic pass/fail against requirements
├── criteria.py                  # Step C rubric definition (weighted criteria list)
├── scorer.py                    # Step C: per-criterion LLM scoring + rationale
├── pipeline.py                  # screen_resume(): single-resume end-to-end scoring
├── batch.py                     # screen_batch(): loops pipeline, ranks candidates
├── fairness.py                  # batch-mode heuristic proxy-correlation check
├── export.py                    # pandas -> CSV bytes for a batch result
├── static/
│   ├── index.html                # single-page shell: login, screening, history tabs
│   ├── style.css                 # dark palette matching sibling repos
│   └── app.js                    # session handling, form submission, rendering
├── sample_data/
│   ├── jds/                      # 8 hand-written job descriptions
│   └── resumes/                  # 26 hand-written resumes across 8 roles
├── tests/
│   ├── test_db.py
│   ├── test_auth.py
│   ├── test_main_auth_routes.py
│   ├── test_resume_parser.py
│   ├── test_requirements_extractor.py
│   ├── test_hard_filters.py
│   ├── test_scorer.py
│   ├── test_pipeline.py
│   ├── test_batch.py
│   ├── test_fairness.py
│   ├── test_export.py
│   ├── test_main_screening_routes.py
│   └── test_sample_data.py
├── pyproject.toml               # existing stub, extended in Task 1
├── render.yaml                  # existing stub, verified in Task 20
├── .env.example                 # existing stub, extended in Task 20
└── README.md                    # rewritten in Task 19
```

---

### Task 1: Project setup & dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `.gitignore` entries for `data/*.db` (if not already covered)

**Interfaces:**
- Produces: `[tool.pytest.ini_options]` config with `pythonpath = ["."]` so all later `tests/test_*.py` files can `import` root-level modules directly (e.g. `from resume_parser import parse_resume`).

- [ ] **Step 1: Add runtime dependencies via uv**

Run:
```bash
cd ~/Developer/ai-recruitment-screener
uv add langchain-core langchain-groq pandas itsdangerous
```

- [ ] **Step 2: Add dev/test dependencies via uv**

Run:
```bash
uv add --dev pytest httpx
```

`httpx` is required by FastAPI's `TestClient`.

- [ ] **Step 3: Add pytest configuration to pyproject.toml**

Open `pyproject.toml` and add this section (create it if absent):

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Verify the environment resolves**

Run: `uv sync`
Expected: completes with no errors, `uv.lock` updated.

- [ ] **Step 5: Check .gitignore covers local artifacts**

Run: `cat .gitignore 2>/dev/null || echo "no .gitignore"`

If `data/`, `.venv/`, `__pycache__/`, `.env` are not already ignored, create/extend `.gitignore`:

```
.venv/
__pycache__/
*.pyc
.env
data/*.db
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore
git commit -m "chore: add LangChain, pandas, auth, and test dependencies"
```

---

### Task 2: SQLite persistence layer

**Files:**
- Create: `db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `db.DB_PATH: Path`, `db.init_db(db_path: Path | None = None) -> None`, `db.save_run(username: str, role: str, jd_text: str, mode: str, result: dict, db_path: Path | None = None) -> int`, `db.get_runs(username: str | None = None, db_path: Path | None = None) -> list[dict]`, `db.get_run(run_id: int, db_path: Path | None = None) -> dict | None`. Each run dict has keys: `id, username, role, jd_text, mode, result, created_at`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Write db.py**

Create `db.py`:

```python
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "screening.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS screening_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    mode TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_db(db_path: Path | None = None) -> None:
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def save_run(
    username: str,
    role: str,
    jd_text: str,
    mode: str,
    result: dict,
    db_path: Path | None = None,
) -> int:
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO screening_runs "
            "(username, role, jd_text, mode, result_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                username,
                role,
                jd_text,
                mode,
                json.dumps(result),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "jd_text": row["jd_text"],
        "mode": row["mode"],
        "result": json.loads(row["result_json"]),
        "created_at": row["created_at"],
    }


def get_runs(username: str | None = None, db_path: Path | None = None) -> list[dict]:
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if username is None:
            rows = conn.execute(
                "SELECT * FROM screening_runs ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM screening_runs WHERE username = ? ORDER BY created_at DESC",
                (username,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_run(run_id: int, db_path: Path | None = None) -> dict | None:
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM screening_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _row_to_dict(row) if row is not None else None
    finally:
        conn.close()
```

Note: `db_path or DB_PATH` re-reads the module-level `DB_PATH` name at call time (not baked in as a default-parameter value), so tests and later tasks can `monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")` and have every function pick it up.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add SQLite persistence for screening runs"
```

---

### Task 3: Auth module

**Files:**
- Create: `auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `os.environ["RECRUITER_PASSWORD"]`, `os.environ["ADMIN_PASSWORD"]`, `os.environ["SESSION_SECRET_KEY"]`
- Produces: `auth.SESSION_MAX_AGE_SECONDS: int`, `auth.verify_password(role: str, password: str) -> bool`, `auth.create_session_token(name: str, role: str) -> str`, `auth.read_session_token(token: str) -> dict | None` (returns `{"name": str, "role": str}`), `auth.login(name: str, role: str, password: str) -> str | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth'`

- [ ] **Step 3: Write auth.py**

Create `auth.py`:

```python
import os

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # 8 hours
VALID_ROLES = ("recruiter", "admin")


def _secret_key() -> str:
    return os.environ.get("SESSION_SECRET_KEY", "dev-insecure-secret-change-me")


def verify_password(role: str, password: str) -> bool:
    stored_plain = os.environ.get(f"{role.upper()}_PASSWORD")
    if not stored_plain:
        return False
    stored_hash = bcrypt.hashpw(stored_plain.encode("utf-8"), bcrypt.gensalt())
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash)


def create_session_token(name: str, role: str) -> str:
    serializer = URLSafeTimedSerializer(_secret_key())
    return serializer.dumps({"name": name, "role": role})


def read_session_token(token: str) -> dict | None:
    serializer = URLSafeTimedSerializer(_secret_key())
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def login(name: str, role: str, password: str) -> str | None:
    role = role.lower()
    if role not in VALID_ROLES:
        return None
    if not verify_password(role, password):
        return None
    return create_session_token(name, role)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: add role-based auth with bcrypt password check and session tokens"
```

---

### Task 4: FastAPI app skeleton — login, logout, session routes

**Files:**
- Create: `main.py`
- Test: `tests/test_main_auth_routes.py`

**Interfaces:**
- Consumes: `auth.login`, `auth.read_session_token`, `auth.SESSION_MAX_AGE_SECONDS`, `db.init_db`
- Produces: `main.app` (FastAPI instance), `main.COOKIE_NAME = "session"`, `main.get_current_user(request: Request) -> dict` (FastAPI dependency, raises 401)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_auth_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main_auth_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write main.py skeleton**

Create `main.py`:

```python
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

import auth
import db

app = FastAPI(title="Zeta Health AI — Resume Screener")

COOKIE_NAME = "session"


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = auth.read_session_token(token)
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return session


class LoginRequest(BaseModel):
    name: str
    role: str
    password: str


@app.post("/login")
def login_route(payload: LoginRequest, response: Response):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    token = auth.login(name, payload.role, payload.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid role or password")
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=auth.SESSION_MAX_AGE_SECONDS,
    )
    return {"name": name, "role": payload.role.lower()}


@app.post("/logout")
def logout_route(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/session")
def session_route(user: dict = Depends(get_current_user)):
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main_auth_routes.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main_auth_routes.py
git commit -m "feat: add FastAPI app skeleton with role-gated session auth"
```

---

### Task 5: Resume parser

**Files:**
- Create: `resume_parser.py`
- Test: `tests/test_resume_parser.py`

**Interfaces:**
- Produces: `resume_parser.CERT_KEYWORDS: list[str]`, `resume_parser.parse_resume(file_bytes: bytes, filename: str) -> dict` returning `{"filename", "candidate_name", "raw_text", "certifications": list[str], "years_experience": float | None, "graduation_year": int | None, "school": str | None, "employment_gap_months": int | None}`

**Sample-data phrasing contract** (used by Task 15): resumes must include a `Name: <Full Name>` first line; a sentence matching `N years of relevant experience` (or `N+ years experience`); for a graduation year, a sentence like `Graduated: YYYY`; for a school, a phrase like `X University` / `University of X` / `X College` / `X Institute`; for an employment gap, `Employment gap: N months`; certifications must appear as exact tokens from `CERT_KEYWORDS`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resume_parser.py`:

```python
from resume_parser import parse_resume

SAMPLE_TEXT = """Name: Priya Nair
RN, ICU
8 years of relevant experience.
Graduated: 2012 from Lakeside University.
Employment gap: 6 months (relocation).
"""


def test_parse_resume_extracts_candidate_name():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["candidate_name"] == "Priya Nair"


def test_parse_resume_extracts_certifications():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert "RN" in result["certifications"]


def test_parse_resume_extracts_years_experience():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["years_experience"] == 8.0


def test_parse_resume_extracts_graduation_year():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["graduation_year"] == 2012


def test_parse_resume_extracts_school():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert "Lakeside University" in result["school"]


def test_parse_resume_school_excludes_graduation_year_and_from():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["school"] == "Lakeside University"


def test_parse_resume_school_matches_across_different_resumes_with_same_school():
    text_a = "Name: A\nGraduated: 1985 from Northgate University.\n5 years of relevant experience."
    text_b = "Name: B\nGraduated: 2023 from Northgate University.\n5 years of relevant experience."
    result_a = parse_resume(text_a.encode("utf-8"), "a.txt")
    result_b = parse_resume(text_b.encode("utf-8"), "b.txt")
    assert result_a["school"] == result_b["school"] == "Northgate University"


def test_parse_resume_extracts_employment_gap():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["employment_gap_months"] == 6


def test_parse_resume_ccs_p_does_not_also_report_bare_ccs():
    text = "Name: Sam Diaz\nCCS-P\n5 years of relevant experience."
    result = parse_resume(text.encode("utf-8"), "sam.txt")
    assert "CCS-P" in result["certifications"]
    assert "CCS" not in result["certifications"]


def test_parse_resume_missing_fields_are_none():
    text = "Name: John Doe\nNo other structured facts here."
    result = parse_resume(text.encode("utf-8"), "john.txt")
    assert result["years_experience"] is None
    assert result["graduation_year"] is None
    assert result["school"] is None
    assert result["employment_gap_months"] is None
    assert result["certifications"] == []


def test_parse_resume_falls_back_to_first_line_for_name():
    text = "Jordan Lee, CPC\n3 years of relevant experience."
    result = parse_resume(text.encode("utf-8"), "jordan.txt")
    assert result["candidate_name"] == "Jordan Lee, CPC"


def test_parse_resume_falls_back_to_filename_for_empty_text():
    result = parse_resume(b"", "empty.txt")
    assert result["candidate_name"] == "empty.txt"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resume_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resume_parser'`

- [ ] **Step 3: Write resume_parser.py**

Create `resume_parser.py`:

```python
import io
import re

import pdfplumber

CERT_KEYWORDS = [
    "RN", "LPN", "BSN", "CPC", "CCS", "CCS-P", "CIC", "COC", "CRC",
    "CPMA", "RHIT", "RHIA", "CDIP", "CCDS", "CPHQ", "CPB",
]


def extract_text(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return file_bytes.decode("utf-8", errors="replace")


def _extract_candidate_name(text: str, filename: str) -> str:
    match = re.search(r"^Name:\s*(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return filename


def _extract_years_experience(text: str) -> float | None:
    matches = re.findall(
        r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s+of)?\s+(?:relevant\s+)?experience",
        text,
        re.IGNORECASE,
    )
    if not matches:
        return None
    return max(float(m) for m in matches)


def _extract_graduation_year(text: str) -> int | None:
    match = re.search(
        r"(?:graduated|graduation)\D{0,20}((?:19|20)\d{2})", text, re.IGNORECASE
    )
    return int(match.group(1)) if match else None


def _extract_school(text: str) -> str | None:
    match = re.search(
        r"University of (?:[A-Z][\w]*\s*){1,4}|"
        r"(?:[A-Z][\w]*\s+){1,4}(?:University|College|Institute)",
        text,
    )
    return match.group(0).strip() if match else None


def _extract_certifications(text: str) -> list[str]:
    return [
        cert
        for cert in CERT_KEYWORDS
        if re.search(rf"\b{re.escape(cert)}\b(?!-)", text)
    ]


def _extract_employment_gap_months(text: str) -> int | None:
    match = re.search(r"employment gap\D{0,20}(\d+)\s*months?", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_resume(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)
    return {
        "filename": filename,
        "candidate_name": _extract_candidate_name(text, filename),
        "raw_text": text,
        "certifications": _extract_certifications(text),
        "years_experience": _extract_years_experience(text),
        "graduation_year": _extract_graduation_year(text),
        "school": _extract_school(text),
        "employment_gap_months": _extract_employment_gap_months(text),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resume_parser.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add resume_parser.py tests/test_resume_parser.py
git commit -m "feat: add resume parser with heuristic structured field extraction"
```

---

### Task 6: JD requirement extractor (Step A)

**Files:**
- Create: `requirements_extractor.py`
- Test: `tests/test_requirements_extractor.py`

**Interfaces:**
- Produces: `requirements_extractor.JDRequirements` (Pydantic model: `required_certifications: list[str]`, `min_years_experience: float`, `required_keywords: list[str]`), `requirements_extractor.get_llm() -> ChatGroq`, `requirements_extractor.extract_requirements(jd_text: str, llm=None) -> JDRequirements`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_requirements_extractor.py`:

```python
from types import SimpleNamespace

from requirements_extractor import JDRequirements, extract_requirements


def _fake_llm(content: str):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_extract_requirements_parses_llm_json():
    fake_llm = _fake_llm(
        '{"required_certifications": ["RN"], '
        '"min_years_experience": 2.0, '
        '"required_keywords": ["ICU", "critical care"]}'
    )
    result = extract_requirements("Need an ICU RN with 2 years experience.", llm=fake_llm)
    assert isinstance(result, JDRequirements)
    assert result.required_certifications == ["RN"]
    assert result.min_years_experience == 2.0
    assert "ICU" in result.required_keywords


def test_extract_requirements_defaults_when_fields_omitted():
    fake_llm = _fake_llm("{}")
    result = extract_requirements("A generic job description.", llm=fake_llm)
    assert result.required_certifications == []
    assert result.min_years_experience == 0.0
    assert result.required_keywords == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_requirements_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'requirements_extractor'`

- [ ] **Step 3: Write requirements_extractor.py**

Create `requirements_extractor.py`:

```python
import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field


class JDRequirements(BaseModel):
    required_certifications: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    required_keywords: list[str] = Field(default_factory=list)


PARSER = PydanticOutputParser(pydantic_object=JDRequirements)

PROMPT = ChatPromptTemplate.from_template(
    "You extract structured hiring requirements from a job description for a "
    "healthcare BPO role (nursing, medical coding, billing, utilization "
    "management, or clinical documentation).\n\n"
    "Job description:\n{jd_text}\n\n"
    "Return ONLY the required certifications/licenses (e.g. RN, CPC, CCS), "
    "the minimum years of relevant experience as a number, and the specialty "
    "keywords a qualified candidate's resume must mention.\n\n"
    "{format_instructions}"
)


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.0,
    )


def extract_requirements(jd_text: str, llm=None) -> JDRequirements:
    llm = llm or get_llm()
    prompt_value = PROMPT.format_prompt(
        jd_text=jd_text, format_instructions=PARSER.get_format_instructions()
    )
    response = llm.invoke(prompt_value.to_messages())
    return PARSER.parse(response.content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_requirements_extractor.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add requirements_extractor.py tests/test_requirements_extractor.py
git commit -m "feat: add LLM-based JD requirement extraction (Step A)"
```

---

### Task 7: Hard filter engine (Step B)

**Files:**
- Create: `hard_filters.py`
- Test: `tests/test_hard_filters.py`

**Interfaces:**
- Consumes: `requirements_extractor.JDRequirements`, a parsed resume dict from `resume_parser.parse_resume`
- Produces: `hard_filters.FilterResult` (Pydantic model: `passed: bool`, `failures: list[str]`), `hard_filters.apply_hard_filters(requirements: JDRequirements, resume: dict) -> FilterResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hard_filters.py`:

```python
from hard_filters import apply_hard_filters
from requirements_extractor import JDRequirements


def _resume(**overrides):
    base = {
        "certifications": ["RN"],
        "years_experience": 5.0,
        "raw_text": "Experienced ICU nurse with critical care background.",
    }
    base.update(overrides)
    return base


def test_passes_when_all_requirements_met():
    requirements = JDRequirements(
        required_certifications=["RN"], min_years_experience=3.0, required_keywords=["ICU"]
    )
    result = apply_hard_filters(requirements, _resume())
    assert result.passed is True
    assert result.failures == []


def test_fails_when_certification_missing():
    requirements = JDRequirements(required_certifications=["CPC"], min_years_experience=0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(certifications=["RN"]))
    assert result.passed is False
    assert "Missing required certification: CPC" in result.failures


def test_fails_when_years_experience_insufficient():
    requirements = JDRequirements(required_certifications=[], min_years_experience=10.0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(years_experience=5.0))
    assert result.passed is False
    assert any("10.0+ years" in f for f in result.failures)


def test_fails_when_years_experience_unknown():
    requirements = JDRequirements(required_certifications=[], min_years_experience=3.0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(years_experience=None))
    assert result.passed is False
    assert any("unknown" in f for f in result.failures)


def test_fails_when_keyword_missing():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=["risk adjustment"])
    result = apply_hard_filters(requirements, _resume(raw_text="General nursing background."))
    assert result.passed is False
    assert "Missing required keyword: risk adjustment" in result.failures


def test_collects_multiple_failures():
    requirements = JDRequirements(
        required_certifications=["CPC"], min_years_experience=10.0, required_keywords=["billing"]
    )
    result = apply_hard_filters(requirements, _resume(certifications=[], years_experience=1.0, raw_text="no relevant terms"))
    assert result.passed is False
    assert len(result.failures) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hard_filters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hard_filters'`

- [ ] **Step 3: Write hard_filters.py**

Create `hard_filters.py`:

```python
from pydantic import BaseModel, Field

from requirements_extractor import JDRequirements


class FilterResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)


def apply_hard_filters(requirements: JDRequirements, resume: dict) -> FilterResult:
    failures: list[str] = []

    resume_certs = {c.upper() for c in resume.get("certifications", [])}
    for cert in requirements.required_certifications:
        if cert.upper() not in resume_certs:
            failures.append(f"Missing required certification: {cert}")

    if requirements.min_years_experience > 0:
        years = resume.get("years_experience")
        if years is None or years < requirements.min_years_experience:
            have = "unknown" if years is None else str(years)
            failures.append(
                f"Requires {requirements.min_years_experience}+ years of relevant "
                f"experience, resume shows {have}"
            )

    resume_text_lower = resume.get("raw_text", "").lower()
    for keyword in requirements.required_keywords:
        if keyword.lower() not in resume_text_lower:
            failures.append(f"Missing required keyword: {keyword}")

    return FilterResult(passed=len(failures) == 0, failures=failures)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hard_filters.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add hard_filters.py tests/test_hard_filters.py
git commit -m "feat: add deterministic hard-filter engine (Step B)"
```

---

### Task 8: Scoring rubric definition

**Files:**
- Create: `criteria.py`

**Interfaces:**
- Produces: `criteria.CRITERIA: list[dict]`, each with keys `id: str, name: str, description: str, weight: float`

- [ ] **Step 1: Write criteria.py**

Create `criteria.py`:

```python
"""criteria.py — weighted soft-scoring rubric (Step C)."""

CRITERIA = [
    {
        "id": "SKL-1",
        "name": "Domain/skills depth",
        "description": (
            "How well does the candidate's demonstrated technical or clinical "
            "skill set match what this role requires, beyond simply listing "
            "keywords?"
        ),
        "weight": 1.5,
    },
    {
        "id": "REL-1",
        "name": "Role relevance",
        "description": (
            "How relevant and substantive is the candidate's past role "
            "experience to this specific job description, not just years "
            "worked?"
        ),
        "weight": 1.5,
    },
    {
        "id": "QUA-1",
        "name": "Resume quality & signal",
        "description": (
            "Does the resume describe concrete accomplishments and "
            "responsibilities, or is it vague/keyword-stuffed with little "
            "real signal?"
        ),
        "weight": 1.0,
    },
    {
        "id": "TRA-1",
        "name": "Career trajectory",
        "description": (
            "Does the candidate's work history show reasonable progression? "
            "Note any gaps with context rather than penalizing them outright, "
            "unless the job description requires continuous employment."
        ),
        "weight": 1.0,
    },
]
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `uv run python -c "from criteria import CRITERIA; print(len(CRITERIA), sum(c['weight'] for c in CRITERIA))"`
Expected: `4 5.0`

- [ ] **Step 3: Commit**

```bash
git add criteria.py
git commit -m "feat: define weighted soft-scoring rubric"
```

---

### Task 9: Soft scorer (Step C)

**Files:**
- Create: `scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Consumes: `criteria.CRITERIA`
- Produces: `scorer.CriterionScore` (Pydantic model: `criterion_id: str, name: str, score: int, rationale: str`), `scorer.get_llm() -> ChatGroq`, `scorer.score_criterion(jd_text: str, resume_text: str, criterion: dict, llm=None) -> CriterionScore`, `scorer.score_all_criteria(jd_text: str, resume_text: str, llm=None) -> list[CriterionScore]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scorer.py`:

```python
from types import SimpleNamespace

from criteria import CRITERIA
from scorer import score_all_criteria, score_criterion


def _fake_llm(content: str):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def _raising_llm():
    def _invoke(messages):
        raise RuntimeError("Groq API timeout")

    return SimpleNamespace(invoke=_invoke)


def test_score_criterion_parses_valid_json():
    fake_llm = _fake_llm('{"score": 4, "rationale": "Strong ICU background matches the role."}')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.criterion_id == CRITERIA[0]["id"]
    assert result.score == 4
    assert "ICU" in result.rationale


def test_score_criterion_strips_markdown_fences():
    fake_llm = _fake_llm('```json\n{"score": 3, "rationale": "Partial match."}\n```')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 3


def test_score_criterion_clamps_out_of_range_score():
    fake_llm = _fake_llm('{"score": 9, "rationale": "Overzealous score."}')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 5


def test_score_criterion_falls_back_on_malformed_json():
    fake_llm = _fake_llm("not valid json at all")
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 1
    assert "Evaluation failed" in result.rationale


def test_score_criterion_falls_back_on_llm_error():
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=_raising_llm())
    assert result.score == 1
    assert "Evaluation failed" in result.rationale


def test_score_all_criteria_scores_every_criterion():
    fake_llm = _fake_llm('{"score": 4, "rationale": "Good match."}')
    results = score_all_criteria("JD text", "Resume text", llm=fake_llm)
    assert len(results) == len(CRITERIA)
    assert {r.criterion_id for r in results} == {c["id"] for c in CRITERIA}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scorer'`

- [ ] **Step 3: Write scorer.py**

Create `scorer.py`:

```python
import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel

from criteria import CRITERIA


class CriterionScore(BaseModel):
    criterion_id: str
    name: str
    score: int
    rationale: str


PROMPT = ChatPromptTemplate.from_template(
    "You are scoring one candidate resume against one job description for a "
    "single evaluation criterion, as part of a healthcare BPO hiring "
    "screener. Be honest — if the resume does not clearly address this "
    "criterion, score it low.\n\n"
    "Job description:\n{jd_text}\n\n"
    "Resume:\n{resume_text}\n\n"
    "Criterion: {criterion_name}\n"
    "What to evaluate: {criterion_description}\n\n"
    "Scoring scale:\n"
    "1 = not addressed at all\n"
    "2 = weak, minimal evidence\n"
    "3 = partially addressed\n"
    "4 = mostly addressed, minor gaps\n"
    "5 = fully and clearly addressed\n\n"
    "Respond with ONLY this JSON object, no markdown, no extra text:\n"
    '{{"score": <integer 1-5>, "rationale": "<2-3 sentence explanation>"}}'
)


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.1,
    )


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def score_criterion(jd_text: str, resume_text: str, criterion: dict, llm=None) -> CriterionScore:
    llm = llm or get_llm()
    try:
        prompt_value = PROMPT.format_prompt(
            jd_text=jd_text,
            resume_text=resume_text,
            criterion_name=criterion["name"],
            criterion_description=criterion["description"],
        )
        response = llm.invoke(prompt_value.to_messages())
        parsed = _parse_json_response(response.content)
        score = max(1, min(5, int(parsed["score"])))
        rationale = str(parsed["rationale"])
    except Exception as exc:
        score = 1
        rationale = f"Evaluation failed ({exc}) — defaulting to lowest score."

    return CriterionScore(
        criterion_id=criterion["id"],
        name=criterion["name"],
        score=score,
        rationale=rationale,
    )


def score_all_criteria(jd_text: str, resume_text: str, llm=None) -> list[CriterionScore]:
    return [score_criterion(jd_text, resume_text, c, llm=llm) for c in CRITERIA]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scorer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scorer.py tests/test_scorer.py
git commit -m "feat: add LLM soft-scoring with rationale and safe-default fallback (Step C)"
```

---

### Task 10: Single-resume pipeline

**Files:**
- Create: `pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `resume_parser.parse_resume`, `hard_filters.apply_hard_filters`, `scorer.score_all_criteria`, `criteria.CRITERIA`, `requirements_extractor.JDRequirements`
- Produces: `pipeline.screen_resume(jd_text: str, requirements: JDRequirements, resume_bytes: bytes, filename: str, llm=None) -> dict` returning `{"filename", "candidate_name", "fit_pct", "hard_filter_passed", "hard_filter_failures", "criterion_scores", "strengths", "gaps", "resume_meta"}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
from types import SimpleNamespace
from unittest.mock import Mock

from pipeline import screen_resume
from requirements_extractor import JDRequirements

RESUME_TEXT = (
    "Name: Priya Nair\n"
    "RN, ICU\n"
    "8 years of relevant experience.\n"
)


def _fake_llm(content='{"score": 4, "rationale": "Solid match."}'):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_screen_resume_short_circuits_on_hard_filter_failure():
    requirements = JDRequirements(
        required_certifications=["CPC"], min_years_experience=0, required_keywords=[]
    )
    llm = Mock()
    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=llm
    )
    assert result["fit_pct"] == 0.0
    assert result["hard_filter_passed"] is False
    assert "Missing required certification: CPC" in result["hard_filter_failures"]
    assert result["gaps"] == result["hard_filter_failures"]
    llm.invoke.assert_not_called()


def test_screen_resume_scores_when_filters_pass():
    requirements = JDRequirements(
        required_certifications=["RN"], min_years_experience=3.0, required_keywords=["ICU"]
    )
    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=_fake_llm()
    )
    assert result["hard_filter_passed"] is True
    assert result["fit_pct"] == 80.0  # every criterion scored 4/5 -> 4/5 * 100
    assert len(result["criterion_scores"]) == 4
    assert result["candidate_name"] == "Priya Nair"


def test_screen_resume_derives_strengths_and_gaps():
    requirements = JDRequirements(
        required_certifications=[], min_years_experience=0, required_keywords=[]
    )

    responses = iter(
        [
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 1, "rationale": "Very weak."}',
            '{"score": 2, "rationale": "Weak."}',
        ]
    )
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=next(responses)))

    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=llm
    )
    assert len(result["strengths"]) == 2
    assert len(result["gaps"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Write pipeline.py**

Create `pipeline.py`:

```python
from criteria import CRITERIA
from hard_filters import apply_hard_filters
from requirements_extractor import JDRequirements
from resume_parser import parse_resume
from scorer import score_all_criteria

STRENGTH_THRESHOLD = 4
GAP_THRESHOLD = 2


def _weighted_fit_pct(criterion_scores) -> float:
    by_id = {cs.criterion_id: cs for cs in criterion_scores}
    weighted_sum = sum(by_id[c["id"]].score * c["weight"] for c in CRITERIA)
    max_weighted = sum(c["weight"] for c in CRITERIA) * 5
    return round((weighted_sum / max_weighted) * 100, 1)


def screen_resume(
    jd_text: str,
    requirements: JDRequirements,
    resume_bytes: bytes,
    filename: str,
    llm=None,
) -> dict:
    resume = parse_resume(resume_bytes, filename)
    filter_result = apply_hard_filters(requirements, resume)

    if not filter_result.passed:
        return {
            "filename": filename,
            "candidate_name": resume["candidate_name"],
            "fit_pct": 0.0,
            "hard_filter_passed": False,
            "hard_filter_failures": filter_result.failures,
            "criterion_scores": [],
            "strengths": [],
            "gaps": filter_result.failures,
            "resume_meta": resume,
        }

    criterion_scores = score_all_criteria(jd_text, resume["raw_text"], llm=llm)
    strengths = [cs.name for cs in criterion_scores if cs.score >= STRENGTH_THRESHOLD]
    gaps = [cs.name for cs in criterion_scores if cs.score <= GAP_THRESHOLD]

    return {
        "filename": filename,
        "candidate_name": resume["candidate_name"],
        "fit_pct": _weighted_fit_pct(criterion_scores),
        "hard_filter_passed": True,
        "hard_filter_failures": [],
        "criterion_scores": [cs.model_dump() for cs in criterion_scores],
        "strengths": strengths,
        "gaps": gaps,
        "resume_meta": resume,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline.py tests/test_pipeline.py
git commit -m "feat: wire hard filters + soft scoring into single-resume pipeline"
```

---

### Task 11: Batch pipeline

**Files:**
- Create: `batch.py`
- Test: `tests/test_batch.py`

**Interfaces:**
- Consumes: `pipeline.screen_resume`, `requirements_extractor.extract_requirements`
- Produces: `batch.screen_batch(jd_text: str, resumes: list[tuple[bytes, str]], llm=None, requirements=None) -> dict` returning `{"requirements": dict, "candidates": list[dict]}` (candidates sorted by `fit_pct` descending)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch.py`:

```python
from types import SimpleNamespace

from batch import screen_batch
from requirements_extractor import JDRequirements

RESUME_A = b"Name: Candidate A\n1 years of relevant experience.\n"
RESUME_B = b"Name: Candidate B\n10 years of relevant experience.\n"


def _fake_llm(content='{"score": 4, "rationale": "Solid match."}'):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_screen_batch_ranks_by_fit_pct_descending():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=[])

    responses = iter(
        [
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
        ]
    )
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=next(responses)))

    result = screen_batch(
        "JD text",
        [(RESUME_A, "a.txt"), (RESUME_B, "b.txt")],
        llm=llm,
        requirements=requirements,
    )
    assert [c["filename"] for c in result["candidates"]] == ["b.txt", "a.txt"]


def test_screen_batch_uses_provided_requirements_without_extraction_call():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=[])
    result = screen_batch(
        "JD text",
        [(RESUME_A, "a.txt")],
        llm=_fake_llm(),
        requirements=requirements,
    )
    assert result["requirements"]["min_years_experience"] == 0
    assert len(result["candidates"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_batch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'batch'`

- [ ] **Step 3: Write batch.py**

Create `batch.py`:

```python
from pipeline import screen_resume
from requirements_extractor import extract_requirements


def screen_batch(
    jd_text: str,
    resumes: list[tuple[bytes, str]],
    llm=None,
    requirements=None,
) -> dict:
    requirements = requirements or extract_requirements(jd_text, llm=llm)
    candidates = [
        screen_resume(jd_text, requirements, resume_bytes, filename, llm=llm)
        for resume_bytes, filename in resumes
    ]
    candidates.sort(key=lambda c: c["fit_pct"], reverse=True)
    return {
        "requirements": requirements.model_dump(),
        "candidates": candidates,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_batch.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add batch.py tests/test_batch.py
git commit -m "feat: add batch pipeline that ranks candidates by fit percentage"
```

---

### Task 12: Fairness check

**Files:**
- Create: `fairness.py`
- Test: `tests/test_fairness.py`

**Interfaces:**
- Consumes: candidate dicts from `batch.screen_batch` (specifically `fit_pct` and `resume_meta`)
- Produces: `fairness.MIN_BATCH_SIZE: int = 5`, `fairness.check_fairness(candidates: list[dict]) -> dict | None` returning `None` or `{"proxy_field": str, "message": str, ...}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fairness.py`:

```python
from fairness import check_fairness


def _candidate(fit_pct, grad_year=None, gap=None, school=None):
    return {
        "fit_pct": fit_pct,
        "resume_meta": {
            "graduation_year": grad_year,
            "employment_gap_months": gap,
            "school": school,
        },
    }


def test_returns_none_below_min_batch_size():
    candidates = [_candidate(80) for _ in range(3)]
    assert check_fairness(candidates) is None


def test_flags_graduation_year_correlation():
    candidates = [
        _candidate(90, grad_year=2020),
        _candidate(85, grad_year=2018),
        _candidate(60, grad_year=2005),
        _candidate(55, grad_year=2000),
        _candidate(40, grad_year=1995),
        _candidate(35, grad_year=1990),
    ]
    result = check_fairness(candidates)
    assert result is not None
    assert result["proxy_field"] == "graduation_year"


def test_returns_none_when_fit_scores_are_uniform():
    candidates = [_candidate(70, grad_year=y) for y in [1990, 1995, 2000, 2005, 2010, 2015]]
    assert check_fairness(candidates) is None


def test_flags_school_group_gap():
    candidates = (
        [_candidate(90, school="Elite University") for _ in range(3)]
        + [_candidate(50, school="State College") for _ in range(3)]
    )
    result = check_fairness(candidates)
    assert result is not None
    assert result["proxy_field"] == "school"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fairness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fairness'`

- [ ] **Step 3: Write fairness.py**

Create `fairness.py`:

```python
from statistics import mean, pstdev

MIN_BATCH_SIZE = 5
NUMERIC_PROXY_FIELDS = ["graduation_year", "employment_gap_months"]
CATEGORICAL_PROXY_FIELDS = ["school"]
CORRELATION_THRESHOLD = 0.5
GROUP_MEAN_GAP_THRESHOLD = 15.0


def _pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mean_x, mean_y = mean(xs), mean(ys)
    std_x, std_y = pstdev(xs), pstdev(ys)
    if std_x == 0 or std_y == 0:
        return None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
    return covariance / (std_x * std_y)


def _categorical_group_gap(candidates: list[dict], field: str):
    groups: dict[str, list[float]] = {}
    for c in candidates:
        value = c.get("resume_meta", {}).get(field)
        if value:
            groups.setdefault(value, []).append(c["fit_pct"])
    means = {k: mean(v) for k, v in groups.items() if len(v) >= 2}
    if len(means) < 2:
        return None
    best = max(means, key=means.get)
    worst = min(means, key=means.get)
    gap = means[best] - means[worst]
    return (gap, best, worst) if gap >= GROUP_MEAN_GAP_THRESHOLD else None


def check_fairness(candidates: list[dict]) -> dict | None:
    if len(candidates) < MIN_BATCH_SIZE:
        return None

    for field in NUMERIC_PROXY_FIELDS:
        pairs = [
            (c["resume_meta"][field], c["fit_pct"])
            for c in candidates
            if c.get("resume_meta", {}).get(field) is not None
        ]
        if len(pairs) < MIN_BATCH_SIZE:
            continue
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        correlation = _pearson_correlation(xs, ys)
        if correlation is not None and abs(correlation) >= CORRELATION_THRESHOLD:
            return {
                "proxy_field": field,
                "correlation": round(correlation, 2),
                "message": (
                    f"Fit scores in this batch show a notable relationship with "
                    f"{field.replace('_', ' ')} — review individual rationales "
                    f"before drawing conclusions."
                ),
            }

    for field in CATEGORICAL_PROXY_FIELDS:
        result = _categorical_group_gap(candidates, field)
        if result:
            gap, best, worst = result
            return {
                "proxy_field": field,
                "gap": round(gap, 1),
                "message": (
                    f"Candidates associated with '{best}' score {round(gap, 1)} "
                    f"points higher on average than those associated with "
                    f"'{worst}' in this batch — review individual rationales "
                    f"before drawing conclusions."
                ),
            }

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fairness.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add fairness.py tests/test_fairness.py
git commit -m "feat: add heuristic fairness proxy check for batch runs"
```

---

### Task 13: CSV export

**Files:**
- Create: `export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: a batch result dict from `batch.screen_batch`
- Produces: `export.batch_to_csv(batch_result: dict) -> bytes`

- [ ] **Step 1: Write the failing test**

Create `tests/test_export.py`:

```python
import csv
import io

from export import batch_to_csv


def _batch_result():
    return {
        "candidates": [
            {
                "candidate_name": "Jane Doe",
                "filename": "jane.txt",
                "fit_pct": 82.5,
                "hard_filter_passed": True,
                "strengths": ["Domain/skills depth"],
                "gaps": [],
            },
            {
                "candidate_name": "John Smith",
                "filename": "john.txt",
                "fit_pct": 0.0,
                "hard_filter_passed": False,
                "strengths": [],
                "gaps": ["Missing required certification: RN"],
            },
        ]
    }


def test_batch_to_csv_includes_all_candidates_and_fields():
    csv_bytes = batch_to_csv(_batch_result())
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert len(rows) == 2
    assert rows[0]["candidate_name"] == "Jane Doe"
    assert rows[0]["fit_pct"] == "82.5"
    assert rows[1]["gaps"] == "Missing required certification: RN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'export'`

- [ ] **Step 3: Write export.py**

Create `export.py`:

```python
import io

import pandas as pd


def batch_to_csv(batch_result: dict) -> bytes:
    rows = [
        {
            "candidate_name": c["candidate_name"],
            "filename": c["filename"],
            "fit_pct": c["fit_pct"],
            "hard_filter_passed": c["hard_filter_passed"],
            "strengths": "; ".join(c["strengths"]),
            "gaps": "; ".join(c["gaps"]),
        }
        for c in batch_result["candidates"]
    ]
    df = pd.DataFrame(rows)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_export.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add export.py tests/test_export.py
git commit -m "feat: add pandas-based CSV export for batch results"
```

---

### Task 14: Screening & history API routes

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_screening_routes.py`

**Interfaces:**
- Consumes: `pipeline.screen_resume`, `batch.screen_batch`, `requirements_extractor.extract_requirements`, `fairness.check_fairness`, `export.batch_to_csv`, `db.save_run`, `db.get_run`, `db.get_runs`
- Produces: routes `POST /screen/single`, `POST /screen/batch`, `GET /export/csv/{run_id}`, `GET /runs`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_screening_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main_screening_routes.py -v`
Expected: FAIL with `AttributeError` / 404s — `/screen/single` etc. don't exist yet

- [ ] **Step 3: Add screening routes to main.py**

First, update the import block at the **top** of `main.py` — replace:

```python
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

import auth
import db
```

with:

```python
import io

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import auth
import db
import export
from batch import screen_batch
from fairness import check_fairness
from pipeline import screen_resume
from requirements_extractor import extract_requirements
```

`HTTPException` is already imported here from Task 4 — do not import it a second time. Then append the following route functions to the **end** of `main.py` (after the existing `session_route` function; nothing else follows it yet):

```python
@app.post("/screen/single")
async def screen_single_route(
    jd_text: str = Form(...),
    resume: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    resume_bytes = await resume.read()
    requirements = extract_requirements(jd_text)
    result = screen_resume(jd_text, requirements, resume_bytes, resume.filename)
    run_id = db.save_run(user["name"], user["role"], jd_text, "single", result)
    return {"run_id": run_id, "result": result}


@app.post("/screen/batch")
async def screen_batch_route(
    jd_text: str = Form(...),
    resumes: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    resume_items = [(await f.read(), f.filename) for f in resumes]
    batch_result = screen_batch(jd_text, resume_items)
    batch_result["fairness_flag"] = check_fairness(batch_result["candidates"])
    run_id = db.save_run(user["name"], user["role"], jd_text, "batch", batch_result)
    return {"run_id": run_id, "result": batch_result}


@app.get("/export/csv/{run_id}")
def export_csv_route(run_id: int, user: dict = Depends(get_current_user)):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["username"] != user["name"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not your run")
    if run["mode"] != "batch":
        raise HTTPException(status_code=400, detail="Only batch runs export to CSV")
    csv_bytes = export.batch_to_csv(run["result"])
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=screening_run_{run_id}.csv"},
    )


@app.get("/runs")
def list_runs_route(user: dict = Depends(get_current_user)):
    if user["role"] == "admin":
        return db.get_runs()
    return db.get_runs(username=user["name"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main_screening_routes.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full test suite so far**

Run: `uv run pytest -v`
Expected: all tests from Tasks 2-14 passed

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main_screening_routes.py
git commit -m "feat: add screening, CSV export, and run-history API routes"
```

---

### Task 15: Sample data — job descriptions & resumes

**Files:**
- Create: `sample_data/jds/*.txt` (8 files)
- Create: `sample_data/resumes/*.txt` (26 files)
- Test: `tests/test_sample_data.py`

**Interfaces:**
- Consumes: `resume_parser.parse_resume` (validates every sample resume parses to non-degenerate fields)
- No new production code interfaces — this task is content authoring plus a verification test.

**Phrasing rules (must follow exactly, per Task 5's contract):**
- Line 1: `Name: <Full Name>`
- Years of experience: a sentence containing `<N> years of relevant experience.` (N can have a decimal, e.g. `2.5`)
- Certifications: bare tokens from `resume_parser.CERT_KEYWORDS` = `RN, LPN, BSN, CPC, CCS, CCS-P, CIC, COC, CRC, CPMA, RHIT, RHIA, CDIP, CCDS, CPHQ, CPB` — include the ones the candidate has; omit the rest.
- Graduation year (only where the category calls for it): `Graduated: <YYYY> from <School Name>.`
- School name (only where the category calls for it): must contain `University`, `College`, or `Institute`.
- Employment gap (only where the category calls for it): `Employment gap: <N> months (<reason>).`
- Everything else is free prose — this is what the LLM soft-scorer reads.
- **For `missing_cert` category resumes specifically:** never spell out the certification abbreviation anywhere in the text, including when describing an in-progress or pending credential — refer to it by full name instead (e.g. "nursing license" or "registered nurse licensure," not "RN"; "professional biller certification," not "CPB"). The certification extractor matches on the bare token with word boundaries, so writing the abbreviation even in a "pending" context will make the file incorrectly show the credential as present.

**Role → required credential/keyword used in that role's JD** (drives the hard filters when screened):

| Role | Required cert | Required keyword | Min years |
|---|---|---|---|
| Registered Nurse | RN | ICU | 3 |
| Medical Biller | CPB | claims submission | 3 |
| Bill Review | CPC | bill audit | 3 |
| IP Coding | CIC | inpatient coding | 3 |
| RA Coding | CRC | risk adjustment | 3 |
| IP QA | CCS | coding quality audit | 3 |
| CDI | CCDS | clinical documentation improvement | 3 |
| Utilization Management | RN | utilization review | 3 |

- [ ] **Step 1: Create the 8 job descriptions**

Create `sample_data/jds/registered_nurse.txt`:

```
Zeta Health AI — Registered Nurse, ICU Step-Down

We are hiring a Registered Nurse for our ICU step-down unit supporting a
high-volume healthcare BPO client. Candidates must hold an active RN license
and bring at least 3 years of relevant experience in acute or critical care.
Direct ICU experience is required — this role floats into ICU coverage during
peak census. Responsibilities include patient assessment, care plan execution,
medication administration, and family communication. Strong documentation
habits and comfort working across a distributed, multi-site care team are
essential.
```

Create `sample_data/jds/medical_biller.txt`:

```
Zeta Health AI — Medical Biller

We need a Medical Biller to handle end-to-end claims submission for a US
healthcare client, from charge entry through payer follow-up. Requires an
active CPB certification and at least 3 years of relevant experience in
medical billing. Must be comfortable with claims submission workflows across
multiple payers, denial management, and basic AR follow-up. Attention to
detail and familiarity with HIPAA-compliant handling of billing data required.
```

Create `sample_data/jds/bill_review.txt`:

```
Zeta Health AI — Bill Review Specialist

We are hiring a Bill Review Specialist to audit coded claims before
submission, catching coding-to-billing mismatches before they become denials.
Requires an active CPC certification and at least 3 years of relevant
experience. Strong bill audit experience is required — this is not a first
coding job, it's a second-pass quality function. Candidates should be
comfortable flagging discrepancies to both coding and billing teams and
documenting audit findings clearly.
```

Create `sample_data/jds/ip_coding.txt`:

```
Zeta Health AI — Inpatient Coder

We are hiring an Inpatient Coder to code complex multi-day inpatient
encounters for a hospital-based healthcare BPO client. Requires an active CIC
certification and at least 3 years of relevant experience. Direct inpatient
coding experience with ICD-10-CM/PCS and DRG assignment is required.
Candidates should be comfortable with high case complexity and tight turnaround
SLAs, and coordinate with CDI when documentation is ambiguous.
```

Create `sample_data/jds/ra_coding.txt`:

```
Zeta Health AI — Risk Adjustment Coder

We are hiring a Risk Adjustment Coder to support HCC coding accuracy for a
Medicare Advantage book of business. Requires an active CRC certification and
at least 3 years of relevant experience. Direct risk adjustment coding
experience is required, including chart chasing, HCC capture, and RADV audit
support. Familiarity with CMS risk adjustment model logic is a strong plus.
```

Create `sample_data/jds/ip_qa.txt`:

```
Zeta Health AI — Inpatient Coding Quality Auditor

We are hiring an Inpatient Coding QA Auditor to perform second-level review of
inpatient coding accuracy across a large coder pool. Requires an active CCS
certification and at least 3 years of relevant experience. Direct coding
quality audit experience is required, including DRG validation, coder
scorecards, and feedback delivery. Strong written communication is essential
since this role drives coder coaching.
```

Create `sample_data/jds/cdi.txt`:

```
Zeta Health AI — Clinical Documentation Integrity Specialist

We are hiring a CDI Specialist to review inpatient documentation concurrently
and issue physician queries where clinical indicators aren't fully captured.
Requires an active CCDS certification and at least 3 years of relevant
experience. Direct clinical documentation improvement experience is required,
including query writing and working DRG reconciliation with coding. Clinical
background (nursing or coding) with strong chart-review instincts preferred.
```

Create `sample_data/jds/utilization_management.txt`:

```
Zeta Health AI — Utilization Management Reviewer

We are hiring a Utilization Management Reviewer to perform prior authorization
and concurrent review for inpatient admissions. Requires an active RN license
and at least 3 years of relevant experience. Direct utilization review
experience is required, including InterQual or MCG criteria application and
payer peer-to-peer coordination. Comfort with high daily review volume and
clear written rationale for determinations is essential.
```

- [ ] **Step 2: Create Registered Nurse resumes (5 files — flagship role, larger set to give the batch/fairness check real signal)**

Create `sample_data/resumes/rn_01_strong_fit.txt`:

```
Name: Priya Nair
RN, BSN
8 years of relevant experience in ICU and step-down care.
Graduated: 2015 from Lakeside University.

Led night-shift ICU coverage for a 20-bed unit, managing ventilator patients
and post-operative cardiac cases. Precepted 6 new graduate nurses. Consistently
rated in the top quartile on unit quality audits. Comfortable with Epic and
Cerner charting systems.
```

Create `sample_data/resumes/rn_02_missing_cert.txt`:

```
Name: Marcus Webb
6 years of relevant experience in med-surg and ICU float coverage.
Graduated: 2017 from Coastal State University.

Currently completing nursing licensure renewal after an interstate move;
credential is in pending status with the new state board. Extensive ICU
float experience covering ventilator management, titrated drips, and post-op
monitoring at a Level II trauma center.
```

Create `sample_data/resumes/rn_03_keyword_stuffed.txt`:

```
Name: Taylor Brooks
RN
4 years of relevant experience.
Graduated: 2019 from Riverside University.

Results-driven, patient-focused, detail-oriented RN. ICU. Critical care.
Patient safety. Quality improvement. Team player. Fast-paced environment.
Strong communicator. Compassionate caregiver. ICU. Evidence-based practice.
Cross-functional collaboration. Committed to excellence.
```

Create `sample_data/resumes/rn_04_fairness_bait_senior.txt`:

```
Name: Eleanor Whitfield
RN, BSN
22 years of relevant experience across ICU, step-down, and charge nurse roles.
Graduated: 1985 from Northgate University.

Charge nurse for a 24-bed ICU for the past 9 years, overseeing staffing,
escalations, and code response. Mentors new hires and coordinates with
hospitalists on complex cases. Deep institutional knowledge of ICU protocols
and interdisciplinary rounding.
```

Create `sample_data/resumes/rn_05_fairness_bait_junior.txt`:

```
Name: Skyler Chen
RN, BSN
3 years of relevant experience in ICU step-down.
Graduated: 2023 from Northgate University.

Completed a 12-month ICU residency program before moving into a permanent
step-down role. Comfortable with vasoactive drips, post-op cardiac monitoring,
and rapid response participation. Actively pursuing CCRN certification.
```

- [ ] **Step 3: Create remaining role resumes (21 files, 3 per role)**

For each row below, write a `sample_data/resumes/<file>` following the phrasing rules from this task's header, expanding the "key facts" into 3-5 sentences of natural prose (same style as the worked RN examples above). Every file starts with `Name: <name>` and states years of relevant experience in the exact phrasing pattern.

**Medical Biller** (JD requires: CPB, "claims submission", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `biller_01_missing_cert.txt` | missing_cert | Name: Devon Marsh. 5 years of relevant experience in claims submission and AR follow-up. No CPB token anywhere (in progress, not yet certified). Mention denial management experience. |
| `biller_02_keyword_stuffed.txt` | keyword_stuffed | Name: Ashley Kim. CPB. 4 years of relevant experience. Heavy buzzword list: "detail-oriented," "results-driven," "claims submission," "revenue cycle," "team player" — minimal concrete detail. |
| `biller_03_career_gap.txt` | career_gap | Name: Robert Nguyen. CPB. 6 years of relevant experience in claims submission across two employers. Employment gap: 14 months (caregiving for a family member). Otherwise solid AR follow-up and denial management background. |

**Bill Review** (JD requires: CPC, "bill audit", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `bill_review_01_keyword_stuffed.txt` | keyword_stuffed | Name: Morgan Ellis. CPC. 5 years of relevant experience. Buzzword-heavy: "quality-focused," "bill audit," "accuracy," "process improvement" repeated with little substance. |
| `bill_review_02_career_gap.txt` | career_gap | Name: Casey Odom. CPC. 7 years of relevant experience in bill audit and coding-to-billing reconciliation. Employment gap: 10 months (further education, completed a health information management certificate). |
| `bill_review_03_wrong_specialty.txt` | wrong_specialty | Name: Felix Grant. CCS (not CPC). 5 years of relevant experience — but entirely in inpatient coding, not billing audit. No mention of "bill audit" anywhere. Strong inpatient coding accomplishments described in detail. |

**IP Coding** (JD requires: CIC, "inpatient coding", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `ip_coding_01_career_gap.txt` | career_gap | Name: Renata Silva. CIC. 6 years of relevant experience in inpatient coding, ICD-10-CM/PCS, DRG assignment. Employment gap: 8 months (relocation). |
| `ip_coding_02_wrong_specialty.txt` | wrong_specialty | Name: Owen Park. CPC (not CIC). 5 years of relevant experience entirely in outpatient professional-fee coding. No inpatient coding or DRG mention. |
| `ip_coding_03_borderline_years.txt` | borderline_years | Name: Lena Vogt. CIC. 3 years of relevant experience in inpatient coding — exactly at the JD's minimum. Solid DRG assignment description, still building complex-case exposure. |

**RA Coding** (JD requires: CRC, "risk adjustment", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `ra_coding_01_wrong_specialty.txt` | wrong_specialty | Name: Ibrahim Yusuf. CIC (not CRC). 6 years of relevant experience entirely in inpatient coding. No risk adjustment or HCC mention. |
| `ra_coding_02_borderline_years.txt` | borderline_years | Name: Grace Malone. CRC. 3 years of relevant experience in risk adjustment coding and HCC capture — exactly at the JD's minimum. |
| `ra_coding_03_overqualified.txt` | overqualified | Name: Harold Prescott. CRC. 18 years of relevant experience in risk adjustment coding, including RADV audit leadership and CMS model expertise. Note: seeking an individual-contributor coding role after stepping back from a management track for better work-life balance. |

**IP QA** (JD requires: CCS, "coding quality audit", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `ip_qa_01_borderline_years.txt` | borderline_years | Name: Nadia Farouk. CCS. 3 years of relevant experience in coding quality audit and DRG validation — exactly at the JD's minimum. |
| `ip_qa_02_overqualified.txt` | overqualified | Name: Walter Higgins. CCS. 20 years of relevant experience in coding quality audit, coder scorecards, and coaching. Note: relocating and looking for a lower-travel individual-contributor role. |
| `ip_qa_03_fairness_bait.txt` | fairness_bait | Name: Dorothy Yang. CCS. 25 years of relevant experience in coding quality audit. Graduated: 1978 from Northgate University. Strong DRG validation and coder feedback track record. |

**CDI** (JD requires: CCDS, "clinical documentation improvement", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `cdi_01_overqualified.txt` | overqualified | Name: Simone Baptiste. CCDS, RN. 16 years of relevant experience in clinical documentation improvement and physician query writing. Note: seeking a fully remote individual-contributor role after a director-level stint. |
| `cdi_02_fairness_bait.txt` | fairness_bait | Name: Herbert Osei. CCDS, RN. 19 years of relevant experience in clinical documentation improvement. Graduated: 1982 from Coastal State University. Detailed working-DRG reconciliation accomplishments. |
| `cdi_03_strong_fit.txt` | strong_fit | Name: Aiko Tanaka. CCDS, RN. 5 years of relevant experience in clinical documentation improvement, concurrent chart review, and physician query writing. Graduated: 2018 from Riverside University. |

**Utilization Management** (JD requires: RN, "utilization review", 3 yrs):

| File | Category | Key facts |
|---|---|---|
| `um_01_fairness_bait.txt` | fairness_bait | Name: Patricia Alvarado. RN. 21 years of relevant experience in utilization review, InterQual criteria, and payer peer-to-peer coordination. Graduated: 1981 from Lakeside University. |
| `um_02_strong_fit.txt` | strong_fit | Name: Jonah Whitmore. RN. 5 years of relevant experience in utilization review, MCG criteria application, and concurrent review. Graduated: 2016 from Coastal State University. |
| `um_03_missing_cert.txt` | missing_cert | Name: Bianca Ortiz. 6 years of relevant experience in utilization review and prior authorization — nursing license currently in renewal/pending status with the state board, not yet active (do not write the bare abbreviation). |

- [ ] **Step 4: Write the verification test**

Create `tests/test_sample_data.py`:

```python
from pathlib import Path

from resume_parser import parse_resume

SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"


def _resume_files():
    return sorted((SAMPLE_DIR / "resumes").glob("*.txt"))


def _jd_files():
    return sorted((SAMPLE_DIR / "jds").glob("*.txt"))


def test_expected_jd_and_resume_counts():
    assert len(_jd_files()) == 8
    assert len(_resume_files()) == 26


def test_every_resume_has_a_real_candidate_name():
    for path in _resume_files():
        parsed = parse_resume(path.read_bytes(), path.name)
        assert parsed["candidate_name"] != path.name, f"{path.name} missing a Name: line"


def test_every_resume_has_years_experience():
    for path in _resume_files():
        parsed = parse_resume(path.read_bytes(), path.name)
        assert parsed["years_experience"] is not None, f"{path.name} missing years-of-experience sentence"


def test_missing_cert_resumes_have_no_role_cert():
    role_cert = {
        "rn_02_missing_cert.txt": "RN",
        "biller_01_missing_cert.txt": "CPB",
        "um_03_missing_cert.txt": "RN",
    }
    for filename, cert in role_cert.items():
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert cert not in parsed["certifications"], f"{filename} should not carry {cert}"


def test_career_gap_resumes_have_gap_months():
    gap_files = ["biller_03_career_gap.txt", "bill_review_02_career_gap.txt", "ip_coding_01_career_gap.txt"]
    for filename in gap_files:
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert parsed["employment_gap_months"] is not None, f"{filename} missing employment gap sentence"


def test_fairness_bait_resumes_have_old_graduation_years():
    bait_files = [
        "rn_04_fairness_bait_senior.txt",
        "ip_qa_03_fairness_bait.txt",
        "cdi_02_fairness_bait.txt",
        "um_01_fairness_bait.txt",
    ]
    for filename in bait_files:
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert parsed["graduation_year"] is not None and parsed["graduation_year"] < 1990, filename
```

- [ ] **Step 5: Run the verification test**

Run: `uv run pytest tests/test_sample_data.py -v`
Expected: 6 passed. If a resume fails a check, fix that file's phrasing to match the rules in this task's header, then rerun.

- [ ] **Step 6: Commit**

```bash
git add sample_data/ tests/test_sample_data.py
git commit -m "feat: add 8-role synthetic sample data with deliberate edge cases"
```

---

### Task 16: Frontend shell — login & session

**Files:**
- Create: `static/index.html`
- Create: `static/style.css`
- Create: `static/app.js`
- Modify: `main.py`

**Interfaces:**
- Consumes: `POST /login`, `POST /logout`, `GET /session`
- Produces: static assets served at `/`; `app.js` exposes a `state` object and `checkSession()` bootstrap call

- [ ] **Step 1: Create static/index.html**

Create `static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Zeta Health AI — Resume Screener</title>
<link rel="stylesheet" href="/style.css" />
</head>
<body>
<div id="disclaimer-banner">
  Synthetic demo data only — not used for real hiring decisions. No real candidate or client information.
</div>

<header id="app-header">
  <h1>Zeta Health AI — Resume Screener</h1>
  <p class="tagline">Clinical operations, intelligently governed.</p>
  <div id="user-bar" class="hidden">
    <span id="user-label"></span>
    <button id="logout-btn">Log out</button>
  </div>
</header>

<section id="login-section">
  <h2>Log in</h2>
  <form id="login-form">
    <label>Your name <input type="text" id="login-name" required /></label>
    <label>Role
      <select id="login-role">
        <option value="recruiter">Recruiter</option>
        <option value="admin">Admin</option>
      </select>
    </label>
    <label>Password <input type="password" id="login-password" required /></label>
    <button type="submit">Log in</button>
  </form>
  <p id="login-error" class="error hidden"></p>
</section>

<nav id="app-nav" class="hidden">
  <button data-tab="screen" class="tab-btn active">Screen Candidates</button>
  <button data-tab="history" class="tab-btn">Run History</button>
</nav>

<section id="screen-tab" class="tab-panel hidden">
  <h2>Screen candidates</h2>
  <p>Upload one resume for a single scorecard, or several for a ranked batch.</p>
  <form id="screen-form">
    <label>Job description
      <textarea id="jd-text" rows="8" required></textarea>
    </label>
    <label>Resume(s) (PDF or .txt)
      <input type="file" id="resume-files" accept=".pdf,.txt" multiple required />
    </label>
    <button type="submit">Run screening</button>
  </form>
  <p id="screen-status" class="hidden"></p>
  <div id="fairness-banner" class="hidden"></div>
  <div id="results-area"></div>
</section>

<section id="history-tab" class="tab-panel hidden">
  <h2>Run history</h2>
  <button id="refresh-history-btn">Refresh</button>
  <div id="history-list"></div>
</section>

<footer>
  <p>Part of the <strong>Zeta Health AI</strong> portfolio of applied AI tools for healthcare BPO operations.</p>
  <p class="tags">healthcare-ai · recruitment · groq · langchain · fastapi · python · healthcare-bpo</p>
</footer>

<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create static/style.css**

Create `static/style.css`:

```css
:root {
  --bg: #0f1a1f;
  --panel: #16242b;
  --text: #e6edf0;
  --muted: #9db3ba;
  --accent: #2c7a4a;
  --danger: #c0392b;
  --warn: #e67e22;
  --border: #263840;
}

* { box-sizing: border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, "Segoe UI", sans-serif;
  margin: 0;
  padding: 0 1.5rem 3rem;
}

#disclaimer-banner {
  background: var(--warn);
  color: #1a1200;
  padding: 0.5rem 1rem;
  text-align: center;
  font-weight: 600;
  margin: 0 -1.5rem 1rem;
}

header#app-header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
}

.tagline { color: var(--muted); margin: 0; }

#user-bar { display: flex; gap: 1rem; align-items: center; margin-top: 0.5rem; }

.hidden { display: none !important; }

nav#app-nav { display: flex; gap: 0.5rem; margin: 1rem 0; }

.tab-btn {
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}

.tab-btn.active { background: var(--accent); }

section, form {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

label { display: block; margin-bottom: 0.75rem; }

input, textarea, select {
  width: 100%;
  padding: 0.5rem;
  margin-top: 0.25rem;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 4px;
}

button {
  background: var(--accent);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
}

.error { color: var(--danger); }

#fairness-banner {
  background: var(--warn);
  color: #1a1200;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}

table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem; border-bottom: 1px solid var(--border); text-align: left; }
tr[data-index] { cursor: pointer; }
tr[data-index]:hover { background: var(--bg); }

.scorecard {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-top: 0.75rem;
}

.fit-pct { font-size: 2rem; font-weight: 700; }

.criterion { margin: 0.5rem 0; padding: 0.5rem; background: var(--bg); border-radius: 4px; }

footer { color: var(--muted); text-align: center; margin-top: 2rem; font-size: 0.85rem; }
```

- [ ] **Step 3: Create static/app.js with login/session handling only**

Create `static/app.js`:

```javascript
const state = { user: null };

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function showApp() {
  document.getElementById("login-section").classList.add("hidden");
  document.getElementById("app-nav").classList.remove("hidden");
  document.getElementById("user-bar").classList.remove("hidden");
  document.getElementById("user-label").textContent = `${state.user.name} (${state.user.role})`;
  document.getElementById("screen-tab").classList.remove("hidden");
}

function showLogin() {
  document.getElementById("login-section").classList.remove("hidden");
  document.getElementById("app-nav").classList.add("hidden");
  document.getElementById("user-bar").classList.add("hidden");
  document.getElementById("screen-tab").classList.add("hidden");
  document.getElementById("history-tab").classList.add("hidden");
}

async function checkSession() {
  try {
    state.user = await api("/session");
    showApp();
  } catch {
    showLogin();
  }
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("login-name").value;
  const role = document.getElementById("login-role").value;
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.classList.add("hidden");
  try {
    state.user = await api("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, role, password }),
    });
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/logout", { method: "POST" });
  state.user = null;
  showLogin();
});

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    document.getElementById(`${btn.dataset.tab}-tab`).classList.remove("hidden");
    if (btn.dataset.tab === "history" && typeof loadHistory === "function") loadHistory();
  });
});

checkSession();
```

- [ ] **Step 4: Mount static files in main.py**

Append to the end of `main.py`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

This must stay the last line in `main.py` — Starlette matches routes in registration order, and the mount would otherwise shadow the API routes registered after it.

Mounting `StaticFiles(directory="static", html=True)` at `"/"` serves every file inside `static/` relative to the root — `static/style.css` at `/style.css`, `static/app.js` at `/app.js`, `static/index.html` at `/` (via `html=True`'s index-file behavior) — not under a `/static/...` prefix. `index.html`'s own `<link>`/`<script>` tags reference `/style.css` and `/app.js` accordingly (already reflected above); do not prefix them with `/static/`.

- [ ] **Step 5: Manual verification**

Run: `uv run uvicorn main:app --reload --port 8000` (requires `RECRUITER_PASSWORD`, `ADMIN_PASSWORD`, `SESSION_SECRET_KEY` set in `.env`)

Open `http://localhost:8000` in a browser and confirm:
- Disclaimer banner, Zeta Health AI header, and tagline render
- Login form appears; logging in with a wrong password shows the error message
- Logging in with the correct Recruiter password shows the nav bar and Screen Candidates tab
- Log out returns to the login form

- [ ] **Step 6: Commit**

```bash
git add static/index.html static/style.css static/app.js main.py
git commit -m "feat: add frontend shell with branded login and session handling"
```

---

### Task 17: Frontend — screening form & scorecard/batch rendering

**Files:**
- Modify: `static/app.js`

**Interfaces:**
- Consumes: `POST /screen/single`, `POST /screen/batch`
- Produces: `renderScorecard(candidate)`, `renderBatchTable(result)` functions; wires `#screen-form` submit handler

- [ ] **Step 1: Append screening logic to static/app.js**

Add to the end of `static/app.js` (before the final `checkSession();` call — move that single line to the very end of the file after this block):

```javascript
function renderScorecard(candidate) {
  const criteria = (candidate.criterion_scores || [])
    .map((cs) => `<div class="criterion"><strong>${cs.name}</strong>: ${cs.score}/5 — ${cs.rationale}</div>`)
    .join("");
  const failures = (candidate.hard_filter_failures || [])
    .map((f) => `<div class="criterion">${f}</div>`)
    .join("");
  return `
    <div class="scorecard">
      <h3>${candidate.candidate_name}</h3>
      <div class="fit-pct">${candidate.fit_pct}%</div>
      ${!candidate.hard_filter_passed ? `<p class="error">Failed hard filters</p>${failures}` : ""}
      ${criteria}
      <p><strong>Strengths:</strong> ${(candidate.strengths || []).join(", ") || "None"}</p>
      <p><strong>Gaps:</strong> ${(candidate.gaps || []).join(", ") || "None"}</p>
    </div>
  `;
}

function renderBatchTable(result) {
  const rows = result.candidates
    .map(
      (c, i) => `
      <tr data-index="${i}">
        <td>${c.candidate_name}</td>
        <td>${c.fit_pct}%</td>
        <td>${c.hard_filter_passed ? "Passed filters" : "Failed filters"}</td>
      </tr>`
    )
    .join("");
  return `
    <table>
      <thead><tr><th>Candidate</th><th>Fit %</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div id="scorecard-detail"></div>
  `;
}

let lastRunId = null;
let lastBatchResult = null;

document.getElementById("screen-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const statusEl = document.getElementById("screen-status");
  const resultsArea = document.getElementById("results-area");
  const fairnessBanner = document.getElementById("fairness-banner");
  fairnessBanner.classList.add("hidden");
  resultsArea.innerHTML = "";
  statusEl.textContent = "Screening in progress…";
  statusEl.classList.remove("hidden");

  const jdText = document.getElementById("jd-text").value;
  const files = document.getElementById("resume-files").files;
  const formData = new FormData();
  formData.append("jd_text", jdText);

  try {
    let payload;
    if (files.length === 1) {
      formData.append("resume", files[0]);
      payload = await api("/screen/single", { method: "POST", body: formData });
      resultsArea.innerHTML = renderScorecard(payload.result);
    } else {
      Array.from(files).forEach((f) => formData.append("resumes", f));
      payload = await api("/screen/batch", { method: "POST", body: formData });
      lastRunId = payload.run_id;
      lastBatchResult = payload.result;
      if (payload.result.fairness_flag) {
        fairnessBanner.textContent = payload.result.fairness_flag.message;
        fairnessBanner.classList.remove("hidden");
      }
      resultsArea.innerHTML = renderBatchTable(payload.result) + `<button id="export-csv-btn">Export CSV</button>`;
      document.querySelectorAll("#results-area tr[data-index]").forEach((row) => {
        row.addEventListener("click", () => {
          const candidate = lastBatchResult.candidates[Number(row.dataset.index)];
          document.getElementById("scorecard-detail").innerHTML = renderScorecard(candidate);
        });
      });
      document.getElementById("export-csv-btn").addEventListener("click", () => {
        window.location.href = `/export/csv/${lastRunId}`;
      });
    }
    statusEl.classList.add("hidden");
  } catch (err) {
    statusEl.textContent = err.message;
  }
});
```

Move the `checkSession();` call (currently the last line of the file) to after this new block, so it remains the final line executed.

- [ ] **Step 2: Manual verification**

Run: `uv run uvicorn main:app --reload --port 8000`

In the browser: log in as Recruiter, paste the contents of `sample_data/jds/registered_nurse.txt` into the JD field, upload `sample_data/resumes/rn_01_strong_fit.txt`. Confirm:
- A single scorecard renders with a fit % and 4 criterion rationales

Then re-submit with all 5 `rn_*.txt` files selected. Confirm:
- A ranked table renders, sorted by fit % descending
- Clicking a row shows that candidate's full scorecard below the table
- An "Export CSV" button appears and downloads a CSV file when clicked

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: wire screening form to single/batch scorecard rendering"
```

---

### Task 18: Frontend — run history tab

**Files:**
- Modify: `static/app.js`

**Interfaces:**
- Consumes: `GET /runs`, `GET /export/csv/{run_id}`
- Produces: `loadHistory()` function, wired to `#refresh-history-btn` and the history tab switch (already referenced by Task 16's tab handler)

- [ ] **Step 1: Append history logic to static/app.js**

Add to `static/app.js`, before the final `checkSession();` call:

```javascript
async function loadHistory() {
  const listEl = document.getElementById("history-list");
  listEl.textContent = "Loading…";
  try {
    const runs = await api("/runs");
    if (runs.length === 0) {
      listEl.textContent = "No screening runs yet.";
      return;
    }
    listEl.innerHTML = runs
      .map(
        (r) => `
        <div class="scorecard">
          <p><strong>${r.username}</strong> (${r.role}) — ${r.mode} — ${new Date(r.created_at).toLocaleString()}</p>
          <p>${r.jd_text.slice(0, 120)}${r.jd_text.length > 120 ? "…" : ""}</p>
          ${r.mode === "batch" ? `<button onclick="window.location.href='/export/csv/${r.id}'">Export CSV</button>` : ""}
        </div>`
      )
      .join("");
  } catch (err) {
    listEl.textContent = err.message;
  }
}

document.getElementById("refresh-history-btn").addEventListener("click", loadHistory);
```

- [ ] **Step 2: Manual verification**

Run: `uv run uvicorn main:app --reload --port 8000`

In the browser: log in as Recruiter, run at least one screening, then click the "Run History" tab. Confirm:
- The run just submitted appears with the correct name, role, mode, and truncated JD text
- Batch runs show an Export CSV button that downloads

Log out, log in as Admin, open Run History. Confirm:
- Admin sees the Recruiter's run too (cross-user visibility)

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: add run history tab with admin cross-user visibility"
```

---

### Task 19: Branding & README

**Files:**
- Modify: `README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Write README.md**

Replace the contents of `README.md`:

```markdown
# Zeta Health AI — Resume Screener

> An AI recruitment screener for high-volume healthcare BPO hiring. Paste a
> job description, upload one or more resumes, and get a structured
> scorecard per candidate — a deterministic hard-filter pass/fail plus an
> LLM-scored, weighted-rubric fit percentage with a rationale for every
> criterion.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-green)
![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange)
![LangChain](https://img.shields.io/badge/LangChain-core%20%2B%20groq-purple)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

> **Synthetic demo data only.** No real candidate information, no real
> Shearwater client names, no connection to any production hiring system.
> This is a portfolio demo, not a hiring decision system.

---

## The Problem

High-volume healthcare BPO hiring (nurses, medical coders, billers,
utilization management reviewers, CDI specialists) means screening dozens of
resumes per requisition against credential and experience requirements that
are non-negotiable — an active license, a specific certification, a minimum
years threshold — before any judgment call about fit even starts. Most
resume screeners either skip the deterministic check entirely (pure LLM
judgment, inconsistent) or bury it inside an opaque score with no reasoning
trail.

## What This Tool Does

Paste a job description and upload resumes (PDF or plain text). Every
resume runs through a two-stage pipeline:

1. **Deterministic hard filters** — required certifications, minimum years
   of experience, and required specialty keywords, extracted from the JD and
   checked in plain Python. No LLM judgment on pass/fail. A failed filter
   short-circuits to a 0% score with the specific reason.
2. **LLM soft-scoring rubric** — for resumes that pass the hard filters, four
   weighted criteria (domain/skills depth, role relevance, resume quality,
   career trajectory) are each scored 1-5 by Groq's `llama-3.3-70b-versatile`
   via LangChain, with a mandatory rationale for every score.

Single resume → one scorecard. Multiple resumes → a ranked batch table with
CSV export and a heuristic fairness check.

## Architecture

```
Login (role-gated: Recruiter / Admin)
                │
JD (paste) + Resume(s) (PDF or .txt, 1 or many)
                │
      Resume Parser (pdfplumber / plain text) ─► structured fields
                │
      JD Requirement Extraction (LangChain + Groq, PydanticOutputParser)
                │
      Hard Filter Stage (pure Python, deterministic)
                │ failed ──► 0%, reason shown
                ▼ passed
      Soft-Scoring Rubric (LangChain + Groq, 4 weighted criteria + rationale)
                │
      Aggregator (pandas) ─► fit %, strengths, gaps ─► persisted (SQLite)
                │
      single ──► scorecard        batch ──► ranked table + fairness check
                │
      Vanilla JS frontend: scorecard / ranked table / CSV export / history
```

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | HTML + CSS + vanilla JS (single-page) |
| LLM orchestration | LangChain (`PydanticOutputParser`, prompt templates) |
| LLM inference | Groq — `llama-3.3-70b-versatile` |
| Resume parsing | pdfplumber |
| Data structuring | pandas |
| Auth | bcrypt + signed session cookie, two roles |
| Persistence | SQLite |
| Language | Python 3.11, `uv` |

## Setup

```bash
git clone https://github.com/zabeelbasheer/ai-recruitment-screener.git
cd ai-recruitment-screener
uv python pin 3.11
uv sync
cp .env.example .env   # add your Groq API key and role passwords
uv run uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`

### `.env`

```
GROQ_API_KEY=your_groq_key_here
MODEL_NAME=llama-3.3-70b-versatile
SESSION_SECRET_KEY=change-me-to-something-random
RECRUITER_PASSWORD=YourRecruiterPassword
ADMIN_PASSWORD=YourAdminPassword
```

## Sample Data

`sample_data/` contains 8 hand-written job descriptions and 26 hand-written
resumes across Registered Nurse, Medical Biller, Bill Review, IP Coding, RA
Coding, IP QA, CDI, and Utilization Management — each resume engineered to
exercise a specific case: strong fit, missing certification, keyword-stuffed,
career gap, wrong specialty, borderline years of experience, overqualified,
or a fairness-check bait case (older graduation year). See
`docs/superpowers/plans/2026-08-14-recruitment-screener.md` (Task 15) for the
full breakdown.

## Fairness Check

Batch runs of 5+ candidates are checked for a heuristic correlation between
fit % and proxy fields already present in parsed resume data — graduation
year, employment-gap length, school name — none of which are inputs to
scoring. If a threshold is crossed, a banner names the proxy field and
recommends reviewing individual rationales. This is an explicit heuristic,
not a compliance-grade bias audit.

## Roadmap

- [ ] Configurable rubric weights per role
- [ ] PDF-per-candidate export alongside CSV
- [ ] Faker-generated large batch for stress-testing ranking at scale
- [ ] Azure AD SSO (MSAL) as a drop-in replacement for env-var auth

## About

Built by [Zabeel M. Basheer](https://linkedin.com/in/zabeelbasheer) — VP
Business Excellence & India Site Lead at Shearwater Health. Part of the
[Zeta Health AI](https://github.com/zabeelbasheer) portfolio of applied AI
tools for healthcare BPO operations.

*Clinical operations, intelligently governed.*

---

## Tags

`healthcare-ai` `recruitment` `hr-tech` `groq` `langchain` `fastapi` `python`
`healthcare-bpo` `hybrid-scoring` `explainable-ai`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with Zeta Health AI branding and full walkthrough"
```

---

### Task 20: End-to-end smoke test & deployment config

**Files:**
- Modify: `.env.example`
- Modify: `render.yaml` (if needed)

**Interfaces:** None — verification and config task.

- [ ] **Step 1: Update .env.example**

Replace the contents of `.env.example`:

```
GROQ_API_KEY=your_groq_key_here
MODEL_NAME=llama-3.3-70b-versatile
SESSION_SECRET_KEY=change-me-to-something-random
RECRUITER_PASSWORD=YourRecruiterPassword
ADMIN_PASSWORD=YourAdminPassword
```

- [ ] **Step 2: Check render.yaml matches the actual start command**

Run: `cat render.yaml`

Confirm the start command is `uvicorn main:app --host 0.0.0.0 --port $PORT` (or equivalent). If it references Streamlit or a different entrypoint, update it to match `main:app`.

- [ ] **Step 3: Run the full automated test suite**

Run: `uv run pytest -v`
Expected: every test from Tasks 2-15 passes (db, auth, main auth routes, resume parser, requirements extractor, hard filters, scorer, pipeline, batch, fairness, export, main screening routes, sample data) — no live LLM calls made.

- [ ] **Step 4: Manual end-to-end smoke test (requires a real GROQ_API_KEY)**

Run: `uv run uvicorn main:app --reload --port 8000`

Walk through:
1. Log in as Recruiter
2. Paste `sample_data/jds/ra_coding.txt`, upload `sample_data/resumes/ra_coding_03_overqualified.txt` alone — confirm a single scorecard with 4 rationale'd criteria
3. Paste `sample_data/jds/registered_nurse.txt`, upload all 5 `sample_data/resumes/rn_*.txt` files — confirm a ranked table, and check whether the fairness banner appears (it may or may not trigger depending on live LLM scoring — that's expected, it's a heuristic)
4. Export CSV from that batch run — confirm the file downloads and opens with all 5 candidates
5. Open Run History as Recruiter — confirm both runs appear
6. Log out, log in as Admin, open Run History — confirm the Recruiter's runs are visible

- [ ] **Step 5: Commit**

```bash
git add .env.example render.yaml
git commit -m "chore: finalize deployment config and env var documentation"
```

---

## Spec Coverage Checklist

| Spec section | Implemented in |
|---|---|
| §3 Stack (FastAPI, vanilla JS, LangChain, Groq, pdfplumber, pandas, bcrypt, SQLite) | Tasks 1, 4, 6, 9, 5, 13, 3, 2 |
| §4 Architecture & data flow | Tasks 10, 11, 14 |
| §5.1 Hard filters | Task 7 |
| §5.2 Soft-scoring rubric | Tasks 8, 9 |
| §5.3 Aggregation | Task 10 |
| §6 Fairness check | Task 12 |
| §7 Auth & persistence | Tasks 2, 3, 4, 14 |
| §8 UI & branding | Tasks 16, 17, 18, 19 |
| §9 Sample data | Task 15 |
| §10 Error handling (parse failure, LLM failure, extraction failure) | Tasks 9 (safe default), 14 (extraction blocks the run on exception, matching spec's "blocks that screening run with a clear message" via the route's natural exception propagation) |
| §11 Testing | Every task's TDD steps + Task 20's full-suite run |
