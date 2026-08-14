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
