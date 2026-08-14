from hard_filters import apply_hard_filters
from requirements_extractor import JDRequirements


def _resume(**overrides):
    base = {
        "certifications": ["RN"],
        "years_experience": 5.0,
        "raw_text": "Experienced ICU nurse with critical care background.",
    }
    base.update(overrides)
    return base


def test_passes_when_all_requirements_met():
    requirements = JDRequirements(
        required_certifications=["RN"], min_years_experience=3.0, required_keywords=["ICU"]
    )
    result = apply_hard_filters(requirements, _resume())
    assert result.passed is True
    assert result.failures == []


def test_fails_when_certification_missing():
    requirements = JDRequirements(required_certifications=["CPC"], min_years_experience=0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(certifications=["RN"]))
    assert result.passed is False
    assert "Missing required certification: CPC" in result.failures


def test_fails_when_years_experience_insufficient():
    requirements = JDRequirements(required_certifications=[], min_years_experience=10.0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(years_experience=5.0))
    assert result.passed is False
    assert any("10.0+ years" in f for f in result.failures)


def test_fails_when_years_experience_unknown():
    requirements = JDRequirements(required_certifications=[], min_years_experience=3.0, required_keywords=[])
    result = apply_hard_filters(requirements, _resume(years_experience=None))
    assert result.passed is False
    assert any("unknown" in f for f in result.failures)


def test_fails_when_keyword_missing():
    requirements = JDRequirements(required_certifications=[], min_years_experience=0, required_keywords=["risk adjustment"])
    result = apply_hard_filters(requirements, _resume(raw_text="General nursing background."))
    assert result.passed is False
    assert "Missing required keyword: risk adjustment" in result.failures


def test_collects_multiple_failures():
    requirements = JDRequirements(
        required_certifications=["CPC"], min_years_experience=10.0, required_keywords=["billing"]
    )
    result = apply_hard_filters(requirements, _resume(certifications=[], years_experience=1.0, raw_text="no relevant terms"))
    assert result.passed is False
    assert len(result.failures) == 3
