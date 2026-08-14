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

To see the fairness banner in this demo, upload all 5 `sample_data/resumes/rn_*.txt`
files together against `sample_data/jds/registered_nurse.txt` — it's the only
sample batch that meets the 5-candidate minimum the heuristic requires.

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
