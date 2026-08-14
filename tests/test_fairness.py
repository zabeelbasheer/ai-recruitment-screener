from fairness import check_fairness


def _candidate(fit_pct, grad_year=None, gap=None, school=None):
    return {
        "fit_pct": fit_pct,
        "resume_meta": {
            "graduation_year": grad_year,
            "employment_gap_months": gap,
            "school": school,
        },
    }


def test_returns_none_below_min_batch_size():
    candidates = [_candidate(80) for _ in range(3)]
    assert check_fairness(candidates) is None


def test_flags_graduation_year_correlation():
    candidates = [
        _candidate(90, grad_year=2020),
        _candidate(85, grad_year=2018),
        _candidate(60, grad_year=2005),
        _candidate(55, grad_year=2000),
        _candidate(40, grad_year=1995),
        _candidate(35, grad_year=1990),
    ]
    result = check_fairness(candidates)
    assert result is not None
    assert result["proxy_field"] == "graduation_year"


def test_returns_none_when_fit_scores_are_uniform():
    candidates = [_candidate(70, grad_year=y) for y in [1990, 1995, 2000, 2005, 2010, 2015]]
    assert check_fairness(candidates) is None


def test_flags_school_group_gap():
    candidates = (
        [_candidate(90, school="Elite University") for _ in range(3)]
        + [_candidate(50, school="State College") for _ in range(3)]
    )
    result = check_fairness(candidates)
    assert result is not None
    assert result["proxy_field"] == "school"
