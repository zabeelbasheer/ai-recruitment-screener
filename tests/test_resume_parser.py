from resume_parser import parse_resume

SAMPLE_TEXT = """Name: Priya Nair
RN, ICU
8 years of relevant experience.
Graduated: 2012 from Lakeside University.
Employment gap: 6 months (relocation).
"""


def test_parse_resume_extracts_candidate_name():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["candidate_name"] == "Priya Nair"


def test_parse_resume_extracts_certifications():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert "RN" in result["certifications"]


def test_parse_resume_extracts_years_experience():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["years_experience"] == 8.0


def test_parse_resume_extracts_graduation_year():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["graduation_year"] == 2012


def test_parse_resume_extracts_school():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert "Lakeside University" in result["school"]


def test_parse_resume_school_excludes_graduation_year_and_from():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["school"] == "Lakeside University"


def test_parse_resume_school_matches_across_different_resumes_with_same_school():
    text_a = "Name: A\nGraduated: 1985 from Northgate University.\n5 years of relevant experience."
    text_b = "Name: B\nGraduated: 2023 from Northgate University.\n5 years of relevant experience."
    result_a = parse_resume(text_a.encode("utf-8"), "a.txt")
    result_b = parse_resume(text_b.encode("utf-8"), "b.txt")
    assert result_a["school"] == result_b["school"] == "Northgate University"


def test_parse_resume_extracts_employment_gap():
    result = parse_resume(SAMPLE_TEXT.encode("utf-8"), "priya.txt")
    assert result["employment_gap_months"] == 6


def test_parse_resume_missing_fields_are_none():
    text = "Name: John Doe\nNo other structured facts here."
    result = parse_resume(text.encode("utf-8"), "john.txt")
    assert result["years_experience"] is None
    assert result["graduation_year"] is None
    assert result["school"] is None
    assert result["employment_gap_months"] is None
    assert result["certifications"] == []


def test_parse_resume_falls_back_to_first_line_for_name():
    text = "Jordan Lee, CPC\n3 years of relevant experience."
    result = parse_resume(text.encode("utf-8"), "jordan.txt")
    assert result["candidate_name"] == "Jordan Lee, CPC"


def test_parse_resume_falls_back_to_filename_for_empty_text():
    result = parse_resume(b"", "empty.txt")
    assert result["candidate_name"] == "empty.txt"
