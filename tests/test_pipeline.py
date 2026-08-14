from types import SimpleNamespace
from unittest.mock import Mock

from pipeline import screen_resume
from requirements_extractor import JDRequirements

RESUME_TEXT = (
    "Name: Priya Nair\n"
    "RN, ICU\n"
    "8 years of relevant experience.\n"
)


def _fake_llm(content='{"score": 4, "rationale": "Solid match."}'):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_screen_resume_short_circuits_on_hard_filter_failure():
    requirements = JDRequirements(
        required_certifications=["CPC"], min_years_experience=0, required_keywords=[]
    )
    llm = Mock()
    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=llm
    )
    assert result["fit_pct"] == 0.0
    assert result["hard_filter_passed"] is False
    assert "Missing required certification: CPC" in result["hard_filter_failures"]
    assert result["gaps"] == result["hard_filter_failures"]
    llm.invoke.assert_not_called()


def test_screen_resume_scores_when_filters_pass():
    requirements = JDRequirements(
        required_certifications=["RN"], min_years_experience=3.0, required_keywords=["ICU"]
    )
    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=_fake_llm()
    )
    assert result["hard_filter_passed"] is True
    assert result["fit_pct"] == 80.0  # every criterion scored 4/5 -> 4/5 * 100
    assert len(result["criterion_scores"]) == 4
    assert result["candidate_name"] == "Priya Nair"


def test_screen_resume_derives_strengths_and_gaps():
    requirements = JDRequirements(
        required_certifications=[], min_years_experience=0, required_keywords=[]
    )

    responses = iter(
        [
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 5, "rationale": "Excellent."}',
            '{"score": 1, "rationale": "Very weak."}',
            '{"score": 2, "rationale": "Weak."}',
        ]
    )
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=next(responses)))

    result = screen_resume(
        "JD text", requirements, RESUME_TEXT.encode("utf-8"), "priya.txt", llm=llm
    )
    assert len(result["strengths"]) == 2
    assert len(result["gaps"]) == 2
