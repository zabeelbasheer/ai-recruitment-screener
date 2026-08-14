import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel

from criteria import CRITERIA


class CriterionScore(BaseModel):
    criterion_id: str
    name: str
    score: int
    rationale: str


PROMPT = ChatPromptTemplate.from_template(
    "You are scoring one candidate resume against one job description for a "
    "single evaluation criterion, as part of a healthcare BPO hiring "
    "screener. Be honest — if the resume does not clearly address this "
    "criterion, score it low.\n\n"
    "Job description:\n{jd_text}\n\n"
    "Resume:\n{resume_text}\n\n"
    "Criterion: {criterion_name}\n"
    "What to evaluate: {criterion_description}\n\n"
    "Scoring scale:\n"
    "1 = not addressed at all\n"
    "2 = weak, minimal evidence\n"
    "3 = partially addressed\n"
    "4 = mostly addressed, minor gaps\n"
    "5 = fully and clearly addressed\n\n"
    "Respond with ONLY this JSON object, no markdown, no extra text:\n"
    '{{"score": <integer 1-5>, "rationale": "<2-3 sentence explanation>"}}'
)


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.1,
    )


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def score_criterion(jd_text: str, resume_text: str, criterion: dict, llm=None) -> CriterionScore:
    try:
        llm = llm or get_llm()
        prompt_value = PROMPT.format_prompt(
            jd_text=jd_text,
            resume_text=resume_text,
            criterion_name=criterion["name"],
            criterion_description=criterion["description"],
        )
        response = llm.invoke(prompt_value.to_messages())
        parsed = _parse_json_response(response.content)
        score = max(1, min(5, int(parsed["score"])))
        rationale = str(parsed["rationale"])
    except Exception as exc:
        score = 1
        rationale = f"Evaluation failed ({exc}) — defaulting to lowest score."

    return CriterionScore(
        criterion_id=criterion["id"],
        name=criterion["name"],
        score=score,
        rationale=rationale,
    )


def score_all_criteria(jd_text: str, resume_text: str, llm=None) -> list[CriterionScore]:
    return [score_criterion(jd_text, resume_text, c, llm=llm) for c in CRITERIA]
