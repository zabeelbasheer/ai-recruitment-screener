import io

import pandas as pd


def batch_to_csv(batch_result: dict) -> bytes:
    rows = [
        {
            "candidate_name": c["candidate_name"],
            "filename": c["filename"],
            "fit_pct": c["fit_pct"],
            "hard_filter_passed": c["hard_filter_passed"],
            "strengths": "; ".join(c["strengths"]),
            "gaps": "; ".join(c["gaps"]),
        }
        for c in batch_result["candidates"]
    ]
    df = pd.DataFrame(rows)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")
