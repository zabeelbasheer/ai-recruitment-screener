from types import SimpleNamespace

from requirements_extractor import JDRequirements, extract_requirements


def _fake_llm(content: str):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def test_extract_requirements_parses_llm_json():
    fake_llm = _fake_llm(
        '{"required_certifications": ["RN"], '
        '"min_years_experience": 2.0, '
        '"required_keywords": ["ICU", "critical care"]}'
    )
    result = extract_requirements("Need an ICU RN with 2 years experience.", llm=fake_llm)
    assert isinstance(result, JDRequirements)
    assert result.required_certifications == ["RN"]
    assert result.min_years_experience == 2.0
    assert "ICU" in result.required_keywords


def test_extract_requirements_defaults_when_fields_omitted():
    fake_llm = _fake_llm("{}")
    result = extract_requirements("A generic job description.", llm=fake_llm)
    assert result.required_certifications == []
    assert result.min_years_experience == 0.0
    assert result.required_keywords == []
