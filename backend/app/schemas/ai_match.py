from pydantic import BaseModel, Field, field_validator


class AIMatchOutput(BaseModel):
    score: int = 0
    explanation: str = ""
    highlights: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: int) -> int:
        try:
            v2 = int(v)
        except Exception:
            return 0
        if v2 < 0:
            return 0
        if v2 > 100:
            return 100
        return v2


class AISectionSummary(BaseModel):
    score: int = 0
    summary: str = ""

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: int) -> int:
        try:
            v2 = int(v)
        except Exception:
            return 0
        if v2 < 0:
            return 0
        if v2 > 100:
            return 100
        return v2


class AISectionedMatch(BaseModel):
    education_summary: AISectionSummary = Field(default_factory=AISectionSummary)
    projects_summary: AISectionSummary = Field(default_factory=AISectionSummary)
    work_experience_summary: AISectionSummary = Field(default_factory=AISectionSummary)
    overall_match_score: int = 0

    @field_validator("overall_match_score")
    @classmethod
    def _clamp_overall(cls, v: int) -> int:
        try:
            v2 = int(v)
        except Exception:
            return 0
        if v2 < 0:
            return 0
        if v2 > 100:
            return 100
        return v2

