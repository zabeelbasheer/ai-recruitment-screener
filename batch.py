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
