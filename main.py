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
