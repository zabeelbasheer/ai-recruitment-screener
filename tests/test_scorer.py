from types import SimpleNamespace

from criteria import CRITERIA
from scorer import score_all_criteria, score_criterion


def _fake_llm(content: str):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=content))


def _raising_llm():
    def _invoke(messages):
        raise RuntimeError("Groq API timeout")

    return SimpleNamespace(invoke=_invoke)


def test_score_criterion_parses_valid_json():
    fake_llm = _fake_llm('{"score": 4, "rationale": "Strong ICU background matches the role."}')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.criterion_id == CRITERIA[0]["id"]
    assert result.score == 4
    assert "ICU" in result.rationale


def test_score_criterion_strips_markdown_fences():
    fake_llm = _fake_llm('```json\n{"score": 3, "rationale": "Partial match."}\n```')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 3


def test_score_criterion_clamps_out_of_range_score():
    fake_llm = _fake_llm('{"score": 9, "rationale": "Overzealous score."}')
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 5


def test_score_criterion_falls_back_on_malformed_json():
    fake_llm = _fake_llm("not valid json at all")
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=fake_llm)
    assert result.score == 1
    assert "Evaluation failed" in result.rationale


def test_score_criterion_falls_back_on_llm_error():
    result = score_criterion("JD text", "Resume text", CRITERIA[0], llm=_raising_llm())
    assert result.score == 1
    assert "Evaluation failed" in result.rationale


def test_score_all_criteria_scores_every_criterion():
    fake_llm = _fake_llm('{"score": 4, "rationale": "Good match."}')
    results = score_all_criteria("JD text", "Resume text", llm=fake_llm)
    assert len(results) == len(CRITERIA)
    assert {r.criterion_id for r in results} == {c["id"] for c in CRITERIA}
