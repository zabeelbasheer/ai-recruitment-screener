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
