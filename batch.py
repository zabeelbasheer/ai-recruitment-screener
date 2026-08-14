from pipeline import screen_resume
from requirements_extractor import extract_requirements


def screen_batch(
    jd_text: str,
    resumes: list[tuple[bytes, str]],
    llm=None,
    requirements=None,
) -> dict:
    requirements = requirements or extract_requirements(jd_text, llm=llm)
    candidates = []
    for resume_bytes, filename in resumes:
        try:
            candidates.append(
                screen_resume(jd_text, requirements, resume_bytes, filename, llm=llm)
            )
        except Exception as exc:
            candidates.append(
                {
                    "filename": filename,
                    "candidate_name": filename,
                    "fit_pct": 0.0,
                    "hard_filter_passed": False,
                    "hard_filter_failures": [f"Could not process this resume: {exc}"],
                    "criterion_scores": [],
                    "strengths": [],
                    "gaps": [f"Could not process this resume: {exc}"],
                    "resume_meta": {},
                    "parse_failed": True,
                }
            )
    candidates.sort(key=lambda c: c["fit_pct"], reverse=True)
    return {
        "requirements": requirements.model_dump(),
        "candidates": candidates,
    }
