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


def get_runs_summary(username: str | None = None, db_path: Path | None = None) -> list[dict]:
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        columns = "id, username, role, jd_text, mode, created_at"
        if username is None:
            rows = conn.execute(
                f"SELECT {columns} FROM screening_runs ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {columns} FROM screening_runs WHERE username = ? ORDER BY created_at DESC",
                (username,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "username": r["username"],
                "role": r["role"],
                "jd_text": r["jd_text"],
                "mode": r["mode"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
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
