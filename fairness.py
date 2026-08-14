from statistics import mean, pstdev

MIN_BATCH_SIZE = 5
NUMERIC_PROXY_FIELDS = ["graduation_year", "employment_gap_months"]
CATEGORICAL_PROXY_FIELDS = ["school"]
CORRELATION_THRESHOLD = 0.5
GROUP_MEAN_GAP_THRESHOLD = 15.0


def _pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mean_x, mean_y = mean(xs), mean(ys)
    std_x, std_y = pstdev(xs), pstdev(ys)
    if std_x == 0 or std_y == 0:
        return None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
    return covariance / (std_x * std_y)


def _categorical_group_gap(candidates: list[dict], field: str):
    groups: dict[str, list[float]] = {}
    for c in candidates:
        value = c.get("resume_meta", {}).get(field)
        if value:
            groups.setdefault(value, []).append(c["fit_pct"])
    means = {k: mean(v) for k, v in groups.items() if len(v) >= 2}
    if len(means) < 2:
        return None
    best = max(means, key=means.get)
    worst = min(means, key=means.get)
    gap = means[best] - means[worst]
    return (gap, best, worst) if gap >= GROUP_MEAN_GAP_THRESHOLD else None


def check_fairness(candidates: list[dict]) -> dict | None:
    if len(candidates) < MIN_BATCH_SIZE:
        return None

    for field in NUMERIC_PROXY_FIELDS:
        pairs = [
            (c["resume_meta"][field], c["fit_pct"])
            for c in candidates
            if c.get("resume_meta", {}).get(field) is not None
        ]
        if len(pairs) < MIN_BATCH_SIZE:
            continue
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        correlation = _pearson_correlation(xs, ys)
        if correlation is not None and abs(correlation) >= CORRELATION_THRESHOLD:
            return {
                "proxy_field": field,
                "correlation": round(correlation, 2),
                "message": (
                    f"Fit scores in this batch show a notable relationship with "
                    f"{field.replace('_', ' ')} — review individual rationales "
                    f"before drawing conclusions."
                ),
            }

    for field in CATEGORICAL_PROXY_FIELDS:
        result = _categorical_group_gap(candidates, field)
        if result:
            gap, best, worst = result
            return {
                "proxy_field": field,
                "gap": round(gap, 1),
                "message": (
                    f"Candidates associated with '{best}' score {round(gap, 1)} "
                    f"points higher on average than those associated with "
                    f"'{worst}' in this batch — review individual rationales "
                    f"before drawing conclusions."
                ),
            }

    return None
