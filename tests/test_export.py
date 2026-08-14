import csv
import io

from export import batch_to_csv


def _batch_result():
    return {
        "candidates": [
            {
                "candidate_name": "Jane Doe",
                "filename": "jane.txt",
                "fit_pct": 82.5,
                "hard_filter_passed": True,
                "strengths": ["Domain/skills depth"],
                "gaps": [],
            },
            {
                "candidate_name": "John Smith",
                "filename": "john.txt",
                "fit_pct": 0.0,
                "hard_filter_passed": False,
                "strengths": [],
                "gaps": ["Missing required certification: RN"],
            },
        ]
    }


def test_batch_to_csv_includes_all_candidates_and_fields():
    csv_bytes = batch_to_csv(_batch_result())
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert len(rows) == 2
    assert rows[0]["candidate_name"] == "Jane Doe"
    assert rows[0]["fit_pct"] == "82.5"
    assert rows[1]["gaps"] == "Missing required certification: RN"
