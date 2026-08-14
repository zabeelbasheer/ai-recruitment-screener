from pydantic import BaseModel, Field

from requirements_extractor import JDRequirements


class FilterResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)


def apply_hard_filters(requirements: JDRequirements, resume: dict) -> FilterResult:
    failures: list[str] = []

    resume_certs = {c.upper() for c in resume.get("certifications", [])}
    for cert in requirements.required_certifications:
        if cert.upper() not in resume_certs:
            failures.append(f"Missing required certification: {cert}")

    if requirements.min_years_experience > 0:
        years = resume.get("years_experience")
        if years is None or years < requirements.min_years_experience:
            have = "unknown" if years is None else str(years)
            failures.append(
                f"Requires {requirements.min_years_experience}+ years of relevant "
                f"experience, resume shows {have}"
            )

    resume_text_lower = resume.get("raw_text", "").lower()
    for keyword in requirements.required_keywords:
        if keyword.lower() not in resume_text_lower:
            failures.append(f"Missing required keyword: {keyword}")

    return FilterResult(passed=len(failures) == 0, failures=failures)
