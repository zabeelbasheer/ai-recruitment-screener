# AI Recruitment Screener — Design Spec

Portfolio-tier AI recruitment screener for high-volume healthcare BPO
hiring. Takes a job description and a set of resumes, returns a structured
scorecard per candidate: fit percentage, strengths, gaps, and a
per-criterion reasoning trace.

**All data is synthetic.** No real candidate information, no real
Shearwater client names, no connection to Zwayam or any production system.
Part of the Zeta Health AI portfolio, alongside `hr-policy-bot` and
`ai-governance-audit-tool`.

## 1. Non-goals

- Not a production hiring system — no real candidate PII, no ATS integration
- Not a compliance-grade bias audit — the fairness check is an explicit
  heuristic, framed as such in the UI
- No user self-registration — two fixed roles via env-var credentials, same
  pattern as `ai-governance-audit-tool`

## 2. Stack

| Component | Technology | Note |
|---|---|---|
| Language / env | Python 3.11, `uv` | |
| Backend | FastAPI + Uvicorn | |
| Frontend | HTML + CSS + vanilla JS, single `index.html` | |
| Orchestration | LangChain | `PydanticOutputParser` + prompt templates on the two LLM scoring calls only |
| LLM | Groq (`llama-3.3-70b-versatile`) | |
| Resume parsing | `pdfplumber` | |
| Data structuring | `pandas` | scorecard aggregation, CSV export |
| Auth | `bcrypt`, env-var passwords, session cookie | two roles: Recruiter, Admin |
| Persistence | SQLite (`db.py`) | screening run history, per-user scoping |
| Config | `python-dotenv` | |

FastAPI + vanilla JS was chosen over Streamlit to match the `hr-policy-bot`
pattern and avoid Streamlit's rendering inconsistencies seen on an earlier
sibling project.

## 3. Architecture & data flow

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
      enforces the JSON contract. See §4.
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
      See §5.
                │
                ▼
      JSON response ─► vanilla JS renders ranked table + scorecard
      drill-down + CSV export. Admin: + cross-recruiter run history.
```

Single-resume scoring (Steps A–C + aggregation) is one function, reused by
both the single-resume flow and the batch loop.

## 4. Scoring engine

### 4.1 Hard filters (Step B)

Deterministic Python, no LLM judgment. Applied against Step A's structured
requirements:

- Required license/certification presence (exact/synonym match against
  parsed resume credentials)
- Minimum years of relevant experience
- Required specialty keyword(s) present

Any failure short-circuits scoring to 0% with the specific reason. This is
the auditable, reproducible half of the pipeline.

### 4.2 Soft-scoring rubric (Step C)

Only runs if hard filters pass. Weighted criteria, each scored 1-5 by the
LLM with a mandatory rationale:

| Criterion | What it captures |
|---|---|
| Domain/skills depth | Relevant technical or clinical skill match beyond keyword presence |
| Role relevance | Quality/relevance of past roles to this specific req, not just years |
| Resume quality & signal | Penalizes vague/keyword-stuffed content that says little concretely |
| Career trajectory | Progression pattern; gaps noted with context, not auto-penalized unless the JD requires continuous employment |

`PydanticOutputParser` enforces the JSON contract. On parse failure or LLM
error, falls back to a safe default (lowest soft score + visible
"evaluation failed" rationale), so a single bad LLM response never crashes
a batch run.

### 4.3 Aggregation

Overall fit % = 0 if any hard filter fails (reason shown), else the weighted
average of soft criteria scaled to 100. Strengths/gaps lists are derived from
which criteria scored ≥4 vs ≤2.

## 5. Fairness check (batch mode, ≥5 candidates)

Rather than inferring protected attributes directly (e.g. from names), the
check compares fit % against proxy fields already present in parsed resume
data:

- Graduation year (age proxy)
- Employment-gap length
- School/institution name

A simple correlation / group-mean-gap check runs across the batch. If a
threshold is crossed, a banner appears above the ranked table naming which
proxy field is implicated, with guidance to review individual rationales
before drawing conclusions. This is an explicit heuristic proxy check, not a
compliance-grade bias audit, and is labeled as such in the UI and README.

## 6. Auth & persistence

- Two roles: **Recruiter** (submit JD + resumes, view own screening runs),
  **Admin** (view all screening runs across recruiters)
- Env-var passwords per role (`RECRUITER_PASSWORD`, `ADMIN_PASSWORD`),
  bcrypt-hashed, session cookie, no registration flow
- SQLite (`db.py`) stores screening runs: JD text, timestamp, submitting
  user, batch results — enables "own vs all" scoping and doubles as run
  history

## 7. UI & branding

- `index.html` + vanilla JS + CSS, FastAPI-served, single-file frontend
- Login page (role-gated)
- Screening page: JD input (paste or PDF), resume upload (single or
  multi-file), submit
- Results — single: one scorecard (fit % headline, hard-filter pass/fail
  badges with reasons, per-criterion breakdown with rationale,
  strengths/gaps)
- Results — batch: fairness banner (if flagged) above a ranked table
  (name, fit %, status); row expands to full scorecard; CSV export button
- Admin tab: cross-recruiter run history, searchable
- Persistent disclaimer banner: "Synthetic demo data only — not used for
  real hiring decisions. No real candidate or client information."
- Branding: Zeta Health AI header, "Clinical operations, intelligently
  governed." tagline

## 8. Sample data

**Roles covered (8):** Registered Nurse, Medical Biller, Bill Review,
IP (Inpatient) Coding, RA (Risk Adjustment) Coding, IP QA, CDI (Clinical
Documentation Integrity), Utilization Management.

**Resumes:** hand-written, each engineered to hit a specific case, rotated
across roles rather than repeated in full for every role:

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
  §5 has real signal to catch

**Job descriptions:** one hand-written JD per role (8 total), each with
explicit required certifications/licenses, minimum years, and specialty
keywords so hard filters (§4.1) have concrete gates to test against.

All checked into `sample_data/`.

## 9. Error handling

- Resume PDF fails to parse → candidate flagged "could not parse," excluded
  from ranking but shown in the batch table with the reason; rest of the
  batch proceeds
- LLM scoring call fails or returns malformed JSON → safe default (lowest
  soft score + visible "evaluation failed" rationale); batch always
  completes
- JD requirement extraction (Step A) fails → blocks that screening run with
  a clear message, since hard filters have nothing to gate on without it

## 10. Testing

- Unit tests (pure Python, no live LLM calls): hard-filter pass/fail logic,
  aggregation math, fairness correlation math
- Integration test for the single-resume pipeline with a mocked LLM response
- Manual checklist: run all sample resumes against all sample JDs, confirm
  each engineered edge case produces the expected outcome
- No live-LLM CI

## 11. Key decisions

| Question | Decision |
|---|---|
| Batch vs single | Single-resume scoring is the core function; batch is a thin loop over it |
| Scoring mechanism | Hybrid: deterministic hard filters + LLM soft scoring |
| Explainability | Always-on per-criterion rationale, not a toggle |
| Synthetic data volume | Hand-written, deliberate edge cases, not generated volume |
| Output format | In-app scorecard + CSV export (no PDF) |
| Fairness framing | Visible disclaimer + heuristic proxy-based bias check |
| UI framework | FastAPI + vanilla JS, not Streamlit |
| Auth | Full role-based auth (Recruiter / Admin) |
| Sample data role coverage | 8 roles, hand-written, rotating edge cases rather than full depth per role |
