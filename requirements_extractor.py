import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field


class JDRequirements(BaseModel):
    required_certifications: list[str] = Field(default_factory=list)
    min_years_experience: float = 0.0
    required_keywords: list[str] = Field(default_factory=list)


PARSER = PydanticOutputParser(pydantic_object=JDRequirements)

PROMPT = ChatPromptTemplate.from_template(
    "You extract structured hiring requirements from a job description for a "
    "healthcare BPO role (nursing, medical coding, billing, utilization "
    "management, or clinical documentation).\n\n"
    "Job description:\n{jd_text}\n\n"
    "Return ONLY the required certifications/licenses (e.g. RN, CPC, CCS), "
    "the minimum years of relevant experience as a number, and the specialty "
    "keywords a qualified candidate's resume must mention.\n\n"
    "{format_instructions}"
)


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.0,
    )


def extract_requirements(jd_text: str, llm=None) -> JDRequirements:
    llm = llm or get_llm()
    prompt_value = PROMPT.format_prompt(
        jd_text=jd_text, format_instructions=PARSER.get_format_instructions()
    )
    response = llm.invoke(prompt_value.to_messages())
    return PARSER.parse(response.content)
