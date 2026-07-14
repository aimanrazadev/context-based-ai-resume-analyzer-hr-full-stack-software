from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.application import Application
from ..models.job import Job
from ..modules.applications.status import normalize_application_status
from ..utils.roles import recruiter_only
from .job_handlers import (
    _job_to_public,
    ai_analysis_payload,
    factual_candidate_summary_from_resume,
    is_evaluative_candidate_summary,
)
from ..models.resume import Resume


router = APIRouter(prefix="/recruiter", tags=["Recruiter"])


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _score(value) -> int:
    return int(value or 0)


def _owned_application_query(db: Session, recruiter_id: int):
    return (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .filter(
            Job.user_id == recruiter_id,
            func.lower(Job.status).in_(["active", "closed"]),
        )
    )


def _status_filter(status: str):
    normalized = normalize_application_status(status)
    if normalized == "not-reviewed":
        return or_(Application.status.is_(None), func.lower(Application.status).in_(["", "not-reviewed"]))
    return func.lower(Application.status) == normalized


def _metric(current: int, previous: int) -> dict:
    return {"current": int(current or 0), "previous": int(previous or 0)}


def _count_between(query, start: datetime, end: datetime | None = None) -> int:
    q = query.filter(Application.created_at >= start)
    if end is not None:
        q = q.filter(Application.created_at < end)
    return int(q.with_entities(func.count(Application.id)).scalar() or 0)


def _application_row(db: Session, app: Application, *, job: Job | None = None, include_job: bool = False) -> dict:
    candidate = app.candidate
    breakdown = None
    try:
        breakdown = json.loads(app.score_breakdown_json) if app.score_breakdown_json else None
    except Exception:
        breakdown = None

    ai_resume_analysis = ai_analysis_payload(db, application_id=int(app.id))
    ai_analysis = ai_resume_analysis if isinstance(ai_resume_analysis, dict) else {}
    candidate_summary = str(ai_analysis.get("candidate_summary") or "").strip()
    if is_evaluative_candidate_summary(candidate_summary):
        resume = db.query(Resume).filter(Resume.id == app.resume_id).first() if app.resume_id else None
        candidate_summary = factual_candidate_summary_from_resume(resume) or ""

    row = {
        "application_id": int(app.id),
        "job_id": int(app.job_id),
        "candidate": {
            "id": int(candidate.id) if candidate else None,
            "name": candidate.name if candidate else None,
            "email": candidate.email if candidate else None,
        },
        "resume_id": app.resume_id,
        "semantic_score": float(app.semantic_score or 0.0),
        "skills_score": float(app.skills_score or 0.0),
        "experience_score": float(app.experience_score or 0.0),
        "ai_score": float(app.ai_score or 0.0),
        "final_score": _score(app.final_score),
        "breakdown": breakdown,
        "ai_explanation": app.ai_explanation,
        "ai_analysis": ai_analysis,
        "status": app.status,
        "created_at": _iso(app.created_at),
        "insights": {
            "matched_skills": (breakdown or {}).get("matched_skills") if isinstance(breakdown, dict) else [],
            "missing_skills": (breakdown or {}).get("missing_skills") if isinstance(breakdown, dict) else [],
            "evidence": (breakdown or {}).get("evidence") if isinstance(breakdown, dict) else [],
            "notes": (breakdown or {}).get("notes") if isinstance(breakdown, dict) else [],
            "candidate_summary": candidate_summary,
            "recruiter_summary": candidate_summary,
            "strengths": ai_analysis.get("strengths") if isinstance(ai_analysis.get("strengths"), list) else [],
            "weaknesses": ai_analysis.get("weaknesses") if isinstance(ai_analysis.get("weaknesses"), list) else [],
            "missing_skills_ai": ai_analysis.get("missing_skills") if isinstance(ai_analysis.get("missing_skills"), list) else [],
            "recommendation": str(ai_analysis.get("recommendation") or "").strip(),
            "reasoning": ai_analysis.get("reasoning") or "",
        },
    }
    if include_job and job:
        row["_job"] = _job_to_public(job)
        row["job_title"] = job.job_title
    return row


@router.get("/dashboard")
def recruiter_dashboard_aggregate(
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    recruiter_id = int(user.get("sub"))
    base = _owned_application_query(db, recruiter_id)
    now = datetime.now()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday = start_today - timedelta(days=1)
    start_week = start_today - timedelta(days=start_today.weekday())
    start_last_week = start_week - timedelta(days=7)
    start_month = start_today.replace(day=1)
    previous_month_last_day = start_month - timedelta(days=1)
    start_last_month = previous_month_last_day.replace(day=1)

    month_base = base.filter(Application.created_at >= start_month)
    last_month_base = base.filter(Application.created_at >= start_last_month, Application.created_at < start_month)

    metrics = {
        "new_applicants": _metric(
            _count_between(base, start_today),
            _count_between(base, start_yesterday, start_today),
        ),
        "applications": _metric(
            _count_between(base, start_week),
            _count_between(base, start_last_week, start_week),
        ),
        "not_reviewed": _metric(
            int(month_base.filter(_status_filter("not-reviewed")).with_entities(func.count(Application.id)).scalar() or 0),
            int(last_month_base.filter(_status_filter("not-reviewed")).with_entities(func.count(Application.id)).scalar() or 0),
        ),
        "shortlisted": _metric(
            int(month_base.filter(_status_filter("shortlisted")).with_entities(func.count(Application.id)).scalar() or 0),
            int(last_month_base.filter(_status_filter("shortlisted")).with_entities(func.count(Application.id)).scalar() or 0),
        ),
        "on_hold": _metric(
            int(month_base.filter(_status_filter("on-hold")).with_entities(func.count(Application.id)).scalar() or 0),
            int(last_month_base.filter(_status_filter("on-hold")).with_entities(func.count(Application.id)).scalar() or 0),
        ),
        "rejected": _metric(
            int(month_base.filter(_status_filter("rejected")).with_entities(func.count(Application.id)).scalar() or 0),
            int(last_month_base.filter(_status_filter("rejected")).with_entities(func.count(Application.id)).scalar() or 0),
        ),
    }

    recent_apps = base.order_by(Application.created_at.desc()).limit(6).all()
    return {
        "success": True,
        "metrics": metrics,
        "recent_candidates": [_application_row(db, app) for app in recent_apps],
    }


@router.get("/jobs")
def recruiter_jobs_aggregate(
    include_stats: bool = Query(default=False),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    recruiter_id = int(user.get("sub"))
    q = db.query(Job).filter(Job.user_id == recruiter_id)
    status_norm = (status or "").strip().lower()
    if status_norm == "drafts":
        status_norm = "draft"
    if status_norm and status_norm != "all":
        q = q.filter(func.lower(Job.status) == status_norm)
    else:
        q = q.filter(func.lower(Job.status).in_(["active", "closed"]))
    q = q.filter(func.lower(Job.status) != "deleted")
    jobs = q.order_by(Job.created_at.desc()).all()
    items = [_job_to_public(job, include_draft=job.status == "draft") for job in jobs]

    counts_rows = (
        db.query(func.lower(Job.status), func.count(Job.id))
        .filter(Job.user_id == recruiter_id, func.lower(Job.status) != "deleted")
        .group_by(func.lower(Job.status))
        .all()
    )
    counts = {"active": 0, "closed": 0, "draft": 0}
    for key, count in counts_rows:
        if key in counts:
            counts[key] = int(count or 0)
    counts["all"] = counts["active"] + counts["closed"]

    if include_stats and jobs:
        job_ids = [int(job.id) for job in jobs]
        stat_rows = (
            db.query(
                Application.job_id,
                func.count(Application.id),
                func.max(Application.final_score),
                func.sum(case((Application.final_score >= 70, 1), else_=0)),
            )
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        stats = {
            int(job_id): {
                "count": int(count or 0),
                "top": int(top or 0),
                "shortlisted": int(shortlisted or 0),
            }
            for job_id, count, top, shortlisted in stat_rows
        }
        for item in items:
            item["stats"] = stats.get(int(item["id"]), {"count": 0, "top": 0, "shortlisted": 0})

    return {"success": True, "jobs": items, "counts": counts}


@router.get("/candidates")
def recruiter_candidates_aggregate(
    job_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sort: str = Query(default="score_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    recruiter_id = int(user.get("sub"))
    jobs = (
        db.query(Job)
        .filter(Job.user_id == recruiter_id, func.lower(Job.status).in_(["active", "closed", "draft"]))
        .order_by(Job.created_at.desc())
        .all()
    )
    job_by_id = {int(job.id): job for job in jobs}

    q = _owned_application_query(db, recruiter_id)
    if job_id and job_id != "all":
        q = q.filter(Application.job_id == int(job_id))
    if status and status != "all":
        q = q.filter(_status_filter(status))

    total = int(q.with_entities(func.count(Application.id)).scalar() or 0)
    if sort == "score_asc":
        q = q.order_by(func.coalesce(Application.final_score, -1).asc(), Application.created_at.desc())
    elif sort == "newest":
        q = q.order_by(Application.created_at.desc())
    elif sort == "oldest":
        q = q.order_by(Application.created_at.asc())
    else:
        q = q.order_by(func.coalesce(Application.final_score, -1).desc(), Application.created_at.desc())

    apps = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "success": True,
        "jobs": [_job_to_public(job, include_draft=job.status == "draft") for job in jobs],
        "candidates": [
            _application_row(db, app, job=job_by_id.get(int(app.job_id)), include_job=True)
            for app in apps
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
