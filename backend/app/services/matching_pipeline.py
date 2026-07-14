from dataclasses import dataclass
from typing import Any

from .scoring_service import score_application


@dataclass(frozen=True)
class MatchResult:
    skills_score: float
    final_score: int
    breakdown: dict[str, Any]


def evaluate_candidate_for_job(
    *,
    job_title: str | None,
    job_description: str | None,
    job_required_skills: list[str] | None,
    resume_structured_json: str | None,
    resume_ai_structured_json: str | None = None,
    semantic_score: float = 0.0,
    ai_recommendation: str | None = None,
) -> MatchResult:
    """Canonical scoring entry point for application matching."""
    skills_score, final_score, breakdown = score_application(
        job_title=job_title,
        job_description=job_description,
        job_required_skills=job_required_skills,
        resume_structured_json=resume_structured_json,
        resume_ai_structured_json=resume_ai_structured_json,
        semantic_score=semantic_score,
        ai_recommendation=ai_recommendation,
    )
    return MatchResult(
        skills_score=skills_score,
        final_score=final_score,
        breakdown=breakdown,
    )
