from pydantic import BaseModel, Field


class AIResumeInsight(BaseModel):
    candidate_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    strength_reasoning: str = ""
    weakness_reasoning: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str = "Review Manually"
    reasoning: str = ""
