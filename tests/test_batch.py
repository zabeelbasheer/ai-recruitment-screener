from types import SimpleNamespace

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
