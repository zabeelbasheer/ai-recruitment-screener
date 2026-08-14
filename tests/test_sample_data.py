from pathlib import Path

from resume_parser import parse_resume

SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"


def _resume_files():
    return sorted((SAMPLE_DIR / "resumes").glob("*.txt"))


def _jd_files():
    return sorted((SAMPLE_DIR / "jds").glob("*.txt"))


def test_expected_jd_and_resume_counts():
    assert len(_jd_files()) == 8
    assert len(_resume_files()) == 26


def test_every_resume_has_a_real_candidate_name():
    for path in _resume_files():
        parsed = parse_resume(path.read_bytes(), path.name)
        assert parsed["candidate_name"] != path.name, f"{path.name} missing a Name: line"


def test_every_resume_has_years_experience():
    for path in _resume_files():
        parsed = parse_resume(path.read_bytes(), path.name)
        assert parsed["years_experience"] is not None, f"{path.name} missing years-of-experience sentence"


def test_missing_cert_resumes_have_no_role_cert():
    role_cert = {
        "rn_02_missing_cert.txt": "RN",
        "biller_01_missing_cert.txt": "CPB",
        "um_03_missing_cert.txt": "RN",
    }
    for filename, cert in role_cert.items():
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert cert not in parsed["certifications"], f"{filename} should not carry {cert}"


def test_career_gap_resumes_have_gap_months():
    gap_files = ["biller_03_career_gap.txt", "bill_review_02_career_gap.txt", "ip_coding_01_career_gap.txt"]
    for filename in gap_files:
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert parsed["employment_gap_months"] is not None, f"{filename} missing employment gap sentence"


def test_fairness_bait_resumes_have_old_graduation_years():
    bait_files = [
        "rn_04_fairness_bait_senior.txt",
        "ip_qa_03_fairness_bait.txt",
        "cdi_02_fairness_bait.txt",
        "um_01_fairness_bait.txt",
    ]
    for filename in bait_files:
        path = SAMPLE_DIR / "resumes" / filename
        parsed = parse_resume(path.read_bytes(), filename)
        assert parsed["graduation_year"] is not None and parsed["graduation_year"] < 1990, filename
