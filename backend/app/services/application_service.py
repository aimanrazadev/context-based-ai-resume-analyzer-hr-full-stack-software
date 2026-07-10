import json
from typing import Any

from sqlalchemy.orm import Session

from ..models.ai_resume_analysis import AIResumeAnalysis


def upsert_ai_resume_analysis(
    db: Session,
    *,
    application_id: int,
    analysis: dict[str, Any],
    metadata: dict[str, Any],
) -> AIResumeAnalysis:
    """Persist the single canonical AI explanation for an application."""
    row = db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).first()
    if row is None:
        row = AIResumeAnalysis(application_id=application_id)
    row.candidate_summary = str(analysis.get("candidate_summary") or "")
    row.strengths_json = json.dumps(analysis.get("strengths") or [], ensure_ascii=False)
    row.weaknesses_json = json.dumps(analysis.get("weaknesses") or [], ensure_ascii=False)
    row.matched_skills_json = json.dumps(analysis.get("matched_skills") or [], ensure_ascii=False)
    row.missing_skills_json = json.dumps(analysis.get("missing_skills") or [], ensure_ascii=False)
    row.recommendation = str(analysis.get("recommendation") or "Review Manually")
    row.reasoning = str(analysis.get("reasoning") or "")
    row.provider = "gemini"
    row.model = str(metadata.get("model") or "") or None
    row.status = str(metadata.get("status") or "success")
    row.error_message = str(metadata.get("error_message") or "") or None
    db.add(row)
    db.flush()
    return row


def ai_analysis_payload(db: Session, *, application_id: int) -> dict[str, Any] | None:
    row = db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).first()
    if row is None:
        return None

    def load_list(raw: str | None) -> list[str]:
        try:
            value = json.loads(raw or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    return {
        "candidate_summary": row.candidate_summary,
        "strengths": load_list(row.strengths_json),
        "weaknesses": load_list(row.weaknesses_json),
        "matched_skills": load_list(row.matched_skills_json),
        "missing_skills": load_list(row.missing_skills_json),
        "recommendation": row.recommendation,
        "reasoning": row.reasoning,
        "status": row.status,
    }


def delete_ai_resume_analysis(db: Session, *, application_id: int) -> None:
    db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).delete(synchronize_session=False)


def backfill_missing_application_scores(db: Session) -> int:
    """Upgrade legacy applications once to the canonical stored scoring formula."""
    from datetime import datetime, timezone

    from ..models.application import Application
    from ..models.resume import Resume
    from .job_service import normalize_required_skills
    from .scoring_service import score_application

    rows = db.query(Application).filter(Application.experience_score.is_(None)).all()
    updated = 0
    recommendation_map = {"strong_yes": "Strong Fit", "yes": "Good Fit", "maybe": "Average Fit", "no": "Weak Fit"}
    for application in rows:
        job = application.job
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first() if application.resume_id else None
        if not job or not resume:
            continue
        ai_payload: dict[str, Any] = {}
        try:
            raw_ai = json.loads(resume.ai_structured_json or "{}")
            ai_payload = raw_ai.get("analysis") if isinstance(raw_ai.get("analysis"), dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            ai_payload = {}
        raw_recommendation = str(ai_payload.get("hiring_recommendation") or "").strip()
        recommendation = recommendation_map.get(raw_recommendation, raw_recommendation.replace("_", " ").title())
        if recommendation not in {"Strong Fit", "Good Fit", "Average Fit", "Review Manually", "Weak Fit"}:
            recommendation = "Review Manually"
        semantic_normalized = float(application.semantic_score or 0.0)
        if semantic_normalized > 1.0:
            semantic_normalized /= 100.0
        skills_score, final_score, breakdown = score_application(
            job_title=job.job_title,
            job_description=job.job_description,
            job_required_skills=normalize_required_skills(job.required_skills),
            resume_structured_json=resume.structured_json,
            resume_ai_structured_json=resume.ai_structured_json,
            semantic_score=semantic_normalized,
            ai_recommendation=recommendation,
        )
        application.semantic_score = round(semantic_normalized * 100.0, 2)
        application.skills_score = skills_score
        application.experience_score = float(breakdown.get("experience_score") or 0.0)
        application.ai_score = float(breakdown.get("ai_score") or 0.0)
        application.final_score = final_score
        application.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
        application.matched_skills_json = json.dumps(breakdown.get("matched_skills") or [], ensure_ascii=False)
        application.missing_skills_json = json.dumps(breakdown.get("missing_skills") or [], ensure_ascii=False)
        application.ranking_explanation = str(ai_payload.get("reasoning") or application.ai_explanation or "")
        application.score_updated_at = datetime.now(timezone.utc)
        analysis = {
            "candidate_summary": ai_payload.get("candidate_summary") or ai_payload.get("recruiter_summary") or application.ai_explanation or "",
            "strengths": ai_payload.get("strengths") or [],
            "weaknesses": ai_payload.get("weaknesses") or [],
            "matched_skills": breakdown.get("matched_skills") or [],
            "missing_skills": breakdown.get("missing_skills") or [],
            "recommendation": recommendation,
            "reasoning": application.ranking_explanation,
        }
        upsert_ai_resume_analysis(db, application_id=int(application.id), analysis=analysis, metadata={"status": "migrated", "model": resume.ai_model})
        updated += 1
    if updated:
        db.commit()
    return updated
