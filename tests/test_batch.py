from types import SimpleNamespace

import batch
from batch import screen_batch
from requirements_extractor import JDRequirements

RESUME_A = b"Name: Candidate A\n1 years of relevant experience.\n"
RESUME_B = b"Name: Candidate B\n10 years of relevant experience.\n"


def _fake_llm(content='{"score": 4, "rationale": "Solid match."}'):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_screen_batch_ranks_by_fit_pct_descending():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=[])

    responses = iter(
        [
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 2, "rationale": "Weak."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
        ]
    )
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=next(responses)))

    result = screen_batch(
        "JD text",
        [(RESUME_A, "a.txt"), (RESUME_B, "b.txt")],
        llm=llm,
        requirements=requirements,
    )
    assert [c["filename"] for c in result["candidates"]] == ["b.txt", "a.txt"]


def test_screen_batch_uses_provided_requirements_without_extraction_call():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=[])
    result = screen_batch(
        "JD text",
        [(RESUME_A, "a.txt")],
        llm=_fake_llm(),
        requirements=requirements,
    )
    assert result["requirements"]["min_years_experience"] == 0
    assert len(result["candidates"]) == 1


def test_screen_batch_isolates_a_single_resume_failure(monkeypatch):
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=[])

    original_screen_resume = batch.screen_resume

    def flaky_screen_resume(jd_text, requirements, resume_bytes, filename, llm=None):
        if filename == "bad.txt":
            raise ValueError("could not parse PDF")
        return original_screen_resume(jd_text, requirements, resume_bytes, filename, llm=llm)

    monkeypatch.setattr(batch, "screen_resume", flaky_screen_resume)

    result = screen_batch(
        "JD text",
        [(RESUME_A, "bad.txt"), (RESUME_B, "b.txt")],
        llm=_fake_llm(),
        requirements=requirements,
    )

    assert len(result["candidates"]) == 2
    by_filename = {c["filename"]: c for c in result["candidates"]}

    failed = by_filename["bad.txt"]
    assert failed["parse_failed"] is True
    assert "could not parse PDF" in failed["gaps"][0]
    assert failed["fit_pct"] == 0.0
    assert failed["hard_filter_passed"] is False

    succeeded = by_filename["b.txt"]
    assert succeeded.get("parse_failed") is None
    assert succeeded["hard_filter_passed"] is True
