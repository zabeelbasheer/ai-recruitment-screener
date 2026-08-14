"""criteria.py — weighted soft-scoring rubric (Step C)."""

CRITERIA = [
    {
        "id": "SKL-1",
        "name": "Domain/skills depth",
        "description": (
            "How well does the candidate's demonstrated technical or clinical "
            "skill set match what this role requires, beyond simply listing "
            "keywords?"
        ),
        "weight": 1.5,
    },
    {
        "id": "REL-1",
        "name": "Role relevance",
        "description": (
            "How relevant and substantive is the candidate's past role "
            "experience to this specific job description, not just years "
            "worked?"
        ),
        "weight": 1.5,
    },
    {
        "id": "QUA-1",
        "name": "Resume quality & signal",
        "description": (
            "Does the resume describe concrete accomplishments and "
            "responsibilities, or is it vague/keyword-stuffed with little "
            "real signal?"
        ),
        "weight": 1.0,
    },
    {
        "id": "TRA-1",
        "name": "Career trajectory",
        "description": (
            "Does the candidate's work history show reasonable progression? "
            "Note any gaps with context rather than penalizing them outright, "
            "unless the job description requires continuous employment."
        ),
        "weight": 1.0,
    },
]
