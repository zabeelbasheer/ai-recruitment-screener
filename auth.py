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
