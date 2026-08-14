# AI Recruitment Screener — Design Spec

**Date:** 2026-08-14
**Repo:** `ai-recruitment-screener` (private GitHub, existing empty stub reused)
**Status:** Approved for planning

## 1. What this is

A portfolio-tier AI recruitment screener. Takes a job description and a set of
resumes, returns a structured scorecard per candidate: fit percentage,
strengths, gaps, and a per-criterion reasoning trace. Modeled on high-volume
healthcare BPO hiring roles.

**All data is synthetic.** No real candidate information, no real Shearwater
client names, no connection to Zwayam or any production system. This is a
demo repo sitting next to the other five sprint projects (`hr-policy-bot`,
`ai-governance-audit-tool`, and three others), not a pilot for actual hiring.

## 2. Non-goals

- Not a production hiring system — no real candidate PII, no integration with
  an ATS
- Not a compliance-grade bias audit — the fairness check is an explicit
  heuristic, framed as such in the UI
- No user self-registration — two fixed roles via env-var credentials, same
  pattern as `ai-governance-audit-tool`

## 3. Stack

| Component | Technology | Note |
|---|---|---|
| Language / env | Python 3.11, `uv` | matches sibling repos |
| Backend | FastAPI + Uvicorn | **changed from Streamlit** — see §3.1 |
| Frontend | HTML + CSS + vanilla JS, single `index.html` | matches `hr-policy-bot`, not `ai-governance-audit-tool` |
| Orchestration | LangChain | used specifically for `PydanticOutputParser` + prompt templates on LLM scoring calls — not wrapped around calls that don't need it |
| LLM | Groq (`llama-3.3-70b-versatile`) for prototyping; optional GPT-4o pass for demo polish | |
| Resume parsing | `pdfplumber` | |
| Data structuring | `pandas` | scorecard aggregation, CSV export |
| Auth | `bcrypt`, env-var passwords, session cookie | two roles: Recruiter, Admin |
| Persistence | SQLite (`db.py`) | screening run history, per-user scoping |
| Config | `python-dotenv` | |
| Deployment | Render.com (`render.yaml` already present in stub) | |

### 3.1 Why FastAPI + vanilla JS instead of Streamlit

The brief's original default was Streamlit, on the assumption that
`hr-policy-bot` set that precedent. On inspection, `hr-policy-bot` is
actually FastAPI + vanilla JS — Streamlit is only used by
`ai-governance-audit-tool`. The user has also had rendering issues with
Streamlit before (logo not rendering correctly), so this project follows the
`hr-policy-bot` pattern instead. This also happens to match the existing
stub's dependencies (`fastapi`, `uvicorn`, `python-multipart`, `bcrypt`),
which don't fit a Streamlit app.

### 3.2 Repo disposition

The empty `~/Developer/ai-recruitment-screener` stub (hello-world `main.py`,
empty `screener.py`/`auth.py`, `render.yaml`, matching `pyproject.toml`) is
reused as-is — same folder, same repo name, same GitHub remote
(`github.com/zabeelbasheer/ai-recruitment-screener`). The brief's proposed
name `recruitment-resume-ai` is not used.

## 4. Architecture & data flow

```
Login (role-gated: Recruiter / Admin)
                │
JD (paste or PDF) + Resume(s) (PDF, 1 or many)
                │
      POST /screen (FastAPI, multipart)
                │
      Resume Parser (pdfplumber) ─► structured resume fields
                │
      ── Step A: Requirement Extraction (LLM, LangChain + Groq) ──
      Reads the JD once per run, returns structured hard requirements:
      required licenses/certifications, minimum years of relevant
      experience, required specialty keywords.
                │
      ── Step B: Hard Filter Stage (pure Python, deterministic) ──
      Checks parsed resume against Step A's requirements.
      Any failed required filter → short-circuit: fit % = 0,
      reason shown (e.g. "Missing required certification: CPC").
      No LLM judgment call on pass/fail.
                │ (all required filters passed)
                ▼
      ── Step C: Soft-Scoring Rubric (LLM, LangChain + Groq) ──
      Weighted criteria, 1-5 each + rationale, PydanticOutputParser
      enforces the JSON contract. See §5.
                │
      ── Aggregator (pandas) ──
      Hard filter results + weighted soft scores → overall fit %,
      strengths list, gaps list. Persisted to SQLite against this run.
                │
      single mode ──► one scorecard
      batch mode  ──► loop per resume (single-resume function reused),
                       rank by fit % descending
                │
      ── Fairness Check (batch only, ≥5 candidates) ──
      See §6.
                │
                ▼
      JSON response ─► vanilla JS renders ranked table + scorecard
      drill-down + CSV export. Admin: + cross-recruiter run history.
```

Single-resume scoring (Steps A–C + aggregation) is one function, reused by
both the single-resume flow and the batch loop.

## 5. Scoring engine

### 5.1 Hard filters (Step B)

Deterministic Python, no LLM judgment. Applied against Step A's structured
requirements:

- Required license/certification presence (exact/synonym match against
  parsed resume credentials)
- Minimum years of relevant experience
- Required specialty keyword(s) present

Any failure short-circuits scoring to 0% with the specific reason. This is
the auditable, reproducible half of the pipeline.

### 5.2 Soft-scoring rubric (Step C)

Only runs if hard filters pass. Same shape as `ai-governance-audit-tool`'s
`criteria.py` / `evaluator.py` pattern — weighted criteria, each scored 1-5
by the LLM with a mandatory 2-3 sentence rationale:

| Criterion | What it captures |
|---|---|
| Domain/skills depth | Relevant technical or clinical skill match beyond keyword presence |
| Role relevance | Quality/relevance of past roles to this specific req, not just years |
| Resume quality & signal | Penalizes vague/keyword-stuffed content that says little concretely |
| Career trajectory | Progression pattern; gaps noted with context, not auto-penalized unless the JD requires continuous employment |

`PydanticOutputParser` enforces the JSON contract. On parse failure or LLM
error, falls back to a safe default (lowest soft score + visible
"evaluation failed" rationale) — mirrors `evaluate_criterion`'s except-branch
so a single bad LLM response never crashes a batch run.

### 5.3 Aggregation

Overall fit % = 0 if any hard filter fails (reason shown), else the weighted
average of soft criteria scaled to 100. Strengths/gaps lists are derived from
which criteria scored ≥4 vs ≤2.

## 6. Fairness check (batch mode, ≥5 candidates)

Rather than inferring protected attributes directly (e.g. from names), the
check compares fit % against proxy fields already present in parsed resume
data:

- Graduation year (age proxy)
- Employment-gap length
- School/institution name

A simple correlation / group-mean-gap check runs across the batch. If a
threshold is crossed, a banner appears above the ranked table naming which
proxy field is implicated, with guidance to review individual rationales
before drawing conclusions. Framed explicitly in the UI and README as a
heuristic proxy check, not a compliance-grade bias audit.

## 7. Auth & persistence

- Two roles: **Recruiter** (submit JD + resumes, view own screening runs),
  **Admin** (view all screening runs across recruiters)
- Env-var passwords per role (`RECRUITER_PASSWORD`, `ADMIN_PASSWORD`),
  bcrypt-hashed, session cookie — no registration flow, same
  drop-in-SSO-ready pattern as `ai-governance-audit-tool/auth.py`
- SQLite (`db.py`) stores screening runs: JD text, timestamp, submitting
  user, batch results — enables "own vs all" scoping and doubles as run
  history (Admin gets a searchable cross-recruiter history view, mirroring
  the governance tool's Audit History Dashboard)

## 8. UI & branding

- `index.html` + vanilla JS + CSS, FastAPI-served, single-file frontend
  pattern matching `hr-policy-bot`
- Dark palette consistent with sibling repos
- Login page (role-gated)
- Screening page: JD input (paste or PDF), resume upload (single or
  multi-file), submit
- Results — single: one scorecard (fit % headline, hard-filter pass/fail
  badges with reasons, per-criterion breakdown with rationale,
  strengths/gaps)
- Results — batch: fairness banner (if flagged) above a ranked table
  (name, fit %, status); row expands to full scorecard; CSV export button
  (pandas → download endpoint)
- Admin tab: cross-recruiter run history, searchable
- Persistent disclaimer banner: "Synthetic demo data only — not used for
  real hiring decisions. No real candidate or client information."
- Branding: Zeta Health AI header, "Clinical operations, intelligently
  governed." tagline, About + Tags footer — matching `hr-policy-bot` and
  `ai-governance-audit-tool`'s README/UI conventions

## 9. Sample data

**Roles covered (8):** Registered Nurse, Medical Biller, Bill Review,
IP (Inpatient) Coding, RA (Risk Adjustment) Coding, IP QA, CDI (Clinical
Documentation Integrity), Utilization Management.

(The brief's original generic "medical coder" role is represented by the two
more specific coding specialties, IP Coding and RA Coding, rather than kept
as a separate catch-all.)

**Resumes:** ~3-4 hand-written resumes per role (~28-32 total), each
engineered to hit a specific case, rotated across roles rather than repeated
in full for every role:

- Overqualified
- Underqualified
- Keyword-stuffed
- Career gap
- Missing required certification
- Wrong specialty
- Borderline years-of-experience
- Strong genuine fit
- Fairness-check bait cases (older graduation year, long employment gap) —
  at least one per role family, concentrated enough that the proxy check in
  §6 has real signal to catch

**Job descriptions:** one hand-written JD per role (8 total), each with
explicit required certifications/licenses, minimum years, and specialty
keywords so hard filters (§5.1) have concrete gates to test against.

All checked into `sample_data/`.

## 10. Error handling

- Resume PDF fails to parse → candidate flagged "could not parse," excluded
  from ranking but shown in the batch table with the reason; rest of the
  batch proceeds
- LLM scoring call fails or returns malformed JSON → safe default (lowest
  soft score + visible "evaluation failed" rationale); batch always
  completes
- JD requirement extraction (Step A) fails → blocks that screening run with
  a clear message, since hard filters have nothing to gate on without it

## 11. Testing

- Unit tests (pure Python, no live LLM calls): hard-filter pass/fail logic,
  aggregation math, fairness correlation math
- Integration test for the single-resume pipeline with a mocked LLM response
- Manual checklist: run all sample resumes against all sample JDs, confirm
  each engineered edge case produces the expected outcome
- No live-LLM CI — matches the no-CI precedent in the sibling repos

## 12. Decision log

| Question | Decision |
|---|---|
| Repo location/name | Reuse existing `ai-recruitment-screener` folder and repo name |
| Batch vs single | Single-resume scoring is the core function; batch is a thin loop over it |
| Scoring mechanism | Hybrid: deterministic hard filters + LLM soft scoring |
| Explainability | Always-on per-criterion rationale, not a toggle |
| Synthetic data volume | Hand-written, deliberate edge cases (not Faker-generated volume) |
| Output format | In-app scorecard + CSV export (no PDF) |
| Fairness framing | Visible disclaimer + heuristic proxy-based bias check |
| UI framework | FastAPI + vanilla JS (not Streamlit) — prior Streamlit rendering issues, matches `hr-policy-bot` and the existing stub's dependencies |
| Auth | Full role-based auth (Recruiter / Admin), matching `ai-governance-audit-tool` |
| Sample data role coverage | 8 roles, ~3-4 resumes each, rotating edge cases rather than full depth per role |

## Caveman + Superpowers scoping

- Before running /superpowers:brainstorm or /superpowers:write-plan, run /caveman off (or lite).
  These phases depend on elaboration; full/ultra compression removes the reasoning that makes them useful.
- Before running /superpowers:execute-plan, or for routine terminal work, run /caveman full.
- If you catch yourself mid-brainstorm in compressed mode, stop and run /caveman off before continuing.