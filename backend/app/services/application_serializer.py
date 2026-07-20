from datetime import datetime
import json

from sqlalchemy.orm import Session

from ..models.application import Application
from ..models.candidate import Candidate
from ..models.job import Job
from ..models.resume import Resume
from ..modules.matching.skills import normalize_required_skills
from ..services.application_service import (
    ai_analysis_payload,
    analysis_conflicts_with_skill_snapshot,
    classify_required_skills_from_resume,
    deterministic_insights_from_resume,
    factual_candidate_summary_from_resume,
    is_evaluative_candidate_summary,
)
from ..utils.json_utils import safe_json_loads


def _date_value(value):
    return value.isoformat() if isinstance(value, datetime) else value


def job_to_public(job: Job, *, include_draft: bool = False) -> dict:
    payload = {
        "id": job.id,
        "title": job.job_title,
        "short_description": getattr(job, "short_description", None),
        "description": job.job_description,
        "location": job.location,
        "salary_range": job.salary_range,
        "salary_currency": getattr(job, "salary_currency", None),
        "salary_min": getattr(job, "salary_min", None),
        "salary_max": getattr(job, "salary_max", None),
        "variable_min": getattr(job, "variable_min", None),
        "variable_max": getattr(job, "variable_max", None),
        "opportunity_type": getattr(job, "opportunity_type", None),
        "min_experience_years": getattr(job, "min_experience_years", None),
        "job_type": getattr(job, "job_type", None),
        "job_site": getattr(job, "job_site", None),
        "openings": getattr(job, "openings", None),
        "perks": safe_json_loads(getattr(job, "perks", None)),
        "non_negotiables": safe_json_loads(getattr(job, "non_negotiables", None)),
        "required_skills": safe_json_loads(getattr(job, "required_skills", None)),
        "additional_preferences": getattr(job, "additional_preferences", None),
        "start_date": _date_value(getattr(job, "start_date", None)),
        "duration": getattr(job, "duration", None),
        "apply_by": _date_value(getattr(job, "apply_by", None)),
        "job_link": job.job_link,
        "created_at": _date_value(job.created_at),
        "status": getattr(job, "status", "active") or "active",
        "created_by": job.user_id,
        "draft_step": getattr(job, "draft_step", 1) or 1,
    }
    if include_draft and getattr(job, "draft_data", None):
        payload["draft_data"] = safe_json_loads(job.draft_data)
    return payload


def application_brief_payload(application: Application) -> dict:
    return {
        "id": int(application.id),
        "job_id": int(application.job_id),
        "candidate_id": int(application.candidate_id),
        "resume_id": int(application.resume_id) if getattr(application, "resume_id", None) else None,
        "status": application.status,
        "created_at": _date_value(getattr(application, "created_at", None)),
    }


def already_applied_response(application: Application) -> dict:
    return {
        "success": True,
        "already_applied": True,
        "application": application_brief_payload(application),
    }


def application_status_payload(application: Application) -> dict:
    return {
        "id": int(application.id),
        "application_id": int(application.id),
        "status": application.status,
        "job_id": int(application.job_id),
        "candidate_id": int(application.candidate_id),
        "final_score": int(application.final_score or 0),
    }


def applied_jobs_payload(applications: list[Application]) -> list[dict]:
    return [
        {
            "application_id": application.id,
            "job": job_to_public(application.job) if application.job else None,
            "status": application.status,
            "created_at": _date_value(application.created_at),
            "final_score": int(application.final_score or 0),
        }
        for application in applications
    ]


def job_required_skills_list(job: Job | None) -> list[str]:
    if not job:
        return []
    return normalize_required_skills(getattr(job, "required_skills", None)) or []


def application_details_payload(*, db: Session, application: Application, candidate: Candidate | None) -> dict:
    job = application.job
    breakdown = safe_json_loads(application.score_breakdown_json, default=None, expected_type=dict)

    resume_meta = None
    resume_row = None
    if application.resume_id:
        resume = db.query(Resume).filter(Resume.id == int(application.resume_id)).first()
        if resume and ((candidate and resume.candidate_id == candidate.id) or not candidate):
            resume_row = resume
            resume_meta = {
                "id": int(resume.id),
                "original_filename": resume.original_filename,
                "content_type": resume.content_type,
                "size_bytes": int(resume.size_bytes or 0),
            }

    analysis = ai_analysis_payload(db, application_id=int(application.id))
    if not isinstance(analysis, dict):
        analysis = {}

    stored_matched = safe_json_loads(application.matched_skills_json, default=[], expected_type=list) or []
    stored_missing = safe_json_loads(application.missing_skills_json, default=[], expected_type=list) or []
    if stored_matched or stored_missing:
        matched_skills = [str(item).strip() for item in stored_matched if str(item or "").strip()]
        missing_skills = [str(item).strip() for item in stored_missing if str(item or "").strip()]
    else:
        required_skills = job_required_skills_list(job)
        live_skill_snapshot = classify_required_skills_from_resume(resume_row, required_skills)
        matched_skills = live_skill_snapshot.get("matched_skills") or []
        missing_skills = live_skill_snapshot.get("missing_skills") or []

    deterministic = deterministic_insights_from_resume(
        resume_row,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
    )

    if is_evaluative_candidate_summary(analysis.get("candidate_summary")) or not str(analysis.get("candidate_summary") or "").strip():
        analysis["candidate_summary"] = deterministic.get("candidate_summary") or factual_candidate_summary_from_resume(resume_row)
    if not (isinstance(analysis.get("strengths"), list) and analysis.get("strengths")):
        analysis["strengths"] = deterministic.get("strengths") or []
    weakness_conflict = analysis_conflicts_with_skill_snapshot(analysis, matched_skills)
    if weakness_conflict or not (isinstance(analysis.get("weaknesses"), list) and analysis.get("weaknesses")):
        analysis["weaknesses"] = deterministic.get("weaknesses") or []
    if not str(analysis.get("strength_reasoning") or "").strip():
        analysis["strength_reasoning"] = deterministic.get("strength_reasoning") or ""
    if weakness_conflict or not str(analysis.get("weakness_reasoning") or "").strip():
        analysis["weakness_reasoning"] = deterministic.get("weakness_reasoning") or ""
    if not str(analysis.get("reasoning") or "").strip():
        analysis["reasoning"] = deterministic.get("reasoning") or ""
    analysis["matched_skills"] = matched_skills
    analysis["missing_skills"] = missing_skills
    analysis["recommendation"] = analysis.get("recommendation") or "Review Manually"
    if isinstance(breakdown, dict):
        breakdown["matched_skills"] = matched_skills
        breakdown["missing_skills"] = missing_skills

    return {
        "id": application.id,
        "job_id": application.job_id,
        "resume_id": application.resume_id,
        "status": application.status,
        "created_at": _date_value(application.created_at),
        "score_updated_at": _date_value(getattr(application, "score_updated_at", None)),
        "ai_explanation": application.ai_explanation,
        "semantic_score": float(application.semantic_score or 0.0),
        "skills_score": float(application.skills_score or 0.0),
        "experience_score": float(application.experience_score or 0.0),
        "ai_score": float(application.ai_score or 0.0),
        "final_score": int(application.final_score or 0),
        "score_breakdown": breakdown,
        "ai_analysis": analysis,
        "job": job_to_public(job) if job else None,
        "resume": resume_meta,
    }


def created_application_response(
    *,
    application: Application,
    job: Job,
    ai_analysis: dict,
    breakdown: dict,
) -> dict:
    return {
        "success": True,
        "already_applied": False,
        "created": True,
        "application": {
            "id": int(application.id),
            "job_id": int(application.job_id),
            "candidate_id": int(application.candidate_id),
            "resume_id": int(application.resume_id),
            "ai_explanation": application.ai_explanation,
            "ai_analysis": ai_analysis,
            "semantic_score": float(application.semantic_score or 0.0),
            "skills_score": float(application.skills_score or 0.0),
            "final_score": int(application.final_score or 0),
            "score_breakdown": breakdown,
            "status": application.status,
            "created_at": _date_value(application.created_at),
        },
        "job": job_to_public(job),
    }
