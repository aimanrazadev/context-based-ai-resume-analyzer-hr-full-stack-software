from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import SessionLocal, get_db
from ..models.application import Application
from ..models.candidate import Candidate
from ..models.embedding import Embedding
from ..models.interview import Interview
from ..models.job import Job
from ..models.resume import Resume
from ..models.user import User
from ..services.resume_analysis import extract_and_clean_resume_text, score_resume_against_job
from ..services.resume_parsing import parse_resume_text
from ..services.ai_job_match import ai_match_resume_to_job
from ..services.ai_resume_structuring import ai_structure_resume
from ..services.embeddings import get_or_create_embedding
from ..services.semantic_similarity import fallback_semantic_similarity, resume_job_similarity
from ..services.scoring_engine import score_application
from ..services.progress_tracker import complete_task, create_task, fail_task, get_task, public_view, update_task
from ..utils.dependencies import get_current_user
from ..utils.roles import candidate_only, recruiter_only
from ..utils.validation import (
    validate_string_field,
    validate_integer_field,
    validate_job_status
)
from ..utils.error_handlers import (
    get_error_message,
    handle_database_error
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/octet-stream",
}
MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5MB


def _job_to_public(job: Job, *, include_draft: bool = False) -> dict:
    # Keep keys aligned with current frontend expectations
    perks_payload = None
    if getattr(job, "perks", None):
        try:
            perks_payload = json.loads(job.perks)
        except Exception:
            perks_payload = None
    non_negotiables_payload = None
    if getattr(job, "non_negotiables", None):
        try:
            non_negotiables_payload = json.loads(job.non_negotiables)
        except Exception:
            non_negotiables_payload = None
    required_skills_payload = None
    if getattr(job, "required_skills", None):
        try:
            required_skills_payload = json.loads(job.required_skills)
        except Exception:
            required_skills_payload = None
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
        "perks": perks_payload,
        "non_negotiables": non_negotiables_payload,
        "required_skills": required_skills_payload,
        "additional_preferences": getattr(job, "additional_preferences", None),
        "screening_availability": getattr(job, "screening_availability", None),
        "screening_phone": getattr(job, "screening_phone", None),
        "start_date": getattr(job, "start_date", None).isoformat() if getattr(job, "start_date", None) and isinstance(getattr(job, "start_date", None), datetime) else getattr(job, "start_date", None),
        "duration": getattr(job, "duration", None),
        "apply_by": getattr(job, "apply_by", None).isoformat() if getattr(job, "apply_by", None) and isinstance(getattr(job, "apply_by", None), datetime) else getattr(job, "apply_by", None),
        "job_link": job.job_link,
        "created_at": job.created_at.isoformat() if isinstance(job.created_at, datetime) else job.created_at,
        "status": getattr(job, "status", "active") or "active",
        "created_by": job.user_id,
        "draft_step": getattr(job, "draft_step", 1) or 1,
    }
    if include_draft and getattr(job, "draft_data", None):
        try:
            payload["draft_data"] = json.loads(job.draft_data)
        except Exception:
            payload["draft_data"] = None
    return payload


class JobCreate(BaseModel):
    # For drafts, fields may be partial. For active jobs, validated at runtime below.
    title: str | None = Field(default=None, min_length=2, max_length=150)
    short_description: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    location: str | None = Field(default=None, max_length=100)
    salary_range: str | None = Field(default=None, max_length=50)
    salary_currency: str | None = Field(default=None, max_length=5)
    salary_min: int | None = None
    salary_max: int | None = None
    variable_min: int | None = None
    variable_max: int | None = None
    opportunity_type: str | None = Field(default=None, max_length=20)
    min_experience_years: int | None = None
    job_type: str | None = Field(default=None, max_length=20)
    job_site: str | None = Field(default=None, max_length=20)
    openings: int | None = None
    perks: dict | None = None
    non_negotiables: list[str] | None = None
    required_skills: list[str] | None = None
    additional_preferences: str | None = Field(default=None, max_length=2000)
    screening_availability: str | None = Field(default=None, max_length=255)
    screening_phone: str | None = Field(default=None, max_length=30)
    start_date: str | None = None  # ISO datetime string
    duration: str | None = Field(default=None, max_length=100)
    apply_by: str | None = None  # ISO datetime string
    job_link: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default="active")  # active/draft/closed
    draft_data: dict | None = None
    draft_step: int | None = Field(default=1, ge=1, le=3)


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    short_description: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    location: str | None = Field(default=None, max_length=100)
    salary_range: str | None = Field(default=None, max_length=50)
    salary_currency: str | None = Field(default=None, max_length=5)
    salary_min: int | None = None
    salary_max: int | None = None
    variable_min: int | None = None
    variable_max: int | None = None
    opportunity_type: str | None = Field(default=None, max_length=20)
    min_experience_years: int | None = None
    job_type: str | None = Field(default=None, max_length=20)
    job_site: str | None = Field(default=None, max_length=20)
    openings: int | None = None
    perks: dict | None = None
    non_negotiables: list[str] | None = None
    required_skills: list[str] | None = None
    additional_preferences: str | None = Field(default=None, max_length=2000)
    screening_availability: str | None = Field(default=None, max_length=255)
    screening_phone: str | None = Field(default=None, max_length=30)
    start_date: str | None = None  # ISO datetime string
    duration: str | None = Field(default=None, max_length=100)
    apply_by: str | None = None  # ISO datetime string
    job_link: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None)  # active/draft/closed
    draft_data: dict | None = None
    draft_step: int | None = Field(default=None, ge=1, le=3)


def _find_or_create_candidate(db: Session, *, user_id: int) -> Candidate:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    candidate = db.query(Candidate).filter(Candidate.email == user.email).first()
    if candidate:
        return candidate

    name = user.name or (user.email.split("@", 1)[0] if user.email else "Candidate")
    candidate = Candidate(name=name, email=user.email)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def _find_candidate_job_application(db: Session, *, candidate_id: int, job_id: int) -> Application | None:
    return (
        db.query(Application)
        .filter(Application.candidate_id == int(candidate_id), Application.job_id == int(job_id))
        .order_by(Application.created_at.asc())
        .first()
    )


def _application_brief_payload(application: Application) -> dict:
    return {
        "id": int(application.id),
        "job_id": int(application.job_id),
        "candidate_id": int(application.candidate_id),
        "resume_id": int(application.resume_id) if getattr(application, "resume_id", None) else None,
        "status": application.status,
        "created_at": application.created_at.isoformat()
        if isinstance(getattr(application, "created_at", None), datetime)
        else getattr(application, "created_at", None),
    }


def _job_required_skills_list(job: Job) -> list[str] | None:
    raw = getattr(job, "required_skills", None)
    if raw is None:
        return None
    if isinstance(raw, list):
        cleaned = [str(x).strip() for x in raw if str(x).strip()]
        return cleaned or None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                cleaned = [str(x).strip() for x in parsed if str(x).strip()]
                return cleaned or None
        except Exception:
            pass
    return None


def _already_applied_response(application: Application) -> dict:
    return {
        "success": True,
        "already_applied": True,
        "application": _application_brief_payload(application),
    }


def _safe_application_status(db: Session, desired: str) -> str | None:
    """
    MySQL schemas often define applications.status as an ENUM with a fixed value set.
    If we insert a value outside the ENUM, MySQL raises "Data truncated" errors
    under strict mode.

    This function tries to pick a value that the DB will accept:
    - If ENUM and desired is allowed -> desired
    - Else prefer common values ('applied', 'pending') if present
    - Else fall back to first ENUM value
    - If VARCHAR(N) and desired too long -> trim / fallback
    - For non-MySQL or on any errors -> desired
    """
    try:
        dialect = getattr(getattr(db, "bind", None), "dialect", None)
        if getattr(dialect, "name", "") != "mysql":
            return desired

        row = db.execute(
            text(
                """
                SELECT COLUMN_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'applications'
                  AND COLUMN_NAME = 'status'
                """
            )
        ).fetchone()
        column_type = (row[0] if row else "") or ""
        ct_low = column_type.lower()

        # ENUM('a','b',...)
        if ct_low.startswith("enum("):
            inner = column_type[len("enum(") : -1]
            # split on commas that separate quoted values
            raw_vals = [v.strip() for v in inner.split(",") if v.strip()]
            vals: list[str] = []
            for v in raw_vals:
                v = v.strip()
                if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                    v = v[1:-1]
                vals.append(v)

            if desired in vals:
                return desired
            for cand in ("applied", "pending", "submitted"):
                if cand in vals:
                    return cand
            return vals[0] if vals else None

        # VARCHAR(N)
        m = re.search(r"varchar\((\d+)\)", ct_low)
        if m:
            n = int(m.group(1))
            if n <= 0:
                return desired
            if len(desired) <= n:
                return desired
            # Prefer common short status if it fits
            for cand in ("applied", "pending", "new"):
                if len(cand) <= n:
                    return cand
            return desired[:n]

        return desired
    except Exception:
        return desired


@router.post("", status_code=201)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    user_id = int(user.get("sub"))
    
    # Validate status
    try:
        status = validate_job_status(payload.status or "active")
    except HTTPException:
        raise

    # If it's not a draft, enforce required fields.
    if status != "draft":
        try:
            title = validate_string_field(
                payload.title, "Title",
                min_length=2, max_length=150, required=True
            )
            description = validate_string_field(
                payload.description, "Description",
                min_length=10, max_length=5000, required=True
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Validation error in create_job: {e}")
            raise HTTPException(status_code=400, detail=get_error_message("invalid_job_data"))
    else:
        # For drafts, title is optional but needs default
        title = (payload.title or "").strip()
        if not title:
            title = "Untitled Draft"
        description = payload.description or ""

    # Validate optional fields
    location = validate_string_field(
        payload.location, "Location",
        min_length=1, max_length=100, required=False
    ) or ""
    salary_range = validate_string_field(
        payload.salary_range, "Salary range",
        min_length=1, max_length=50, required=False
    ) or ""
    salary_currency = validate_string_field(
        payload.salary_currency, "Salary currency",
        min_length=1, max_length=5, required=False
    )
    opportunity_type = validate_string_field(
        payload.opportunity_type, "Opportunity type",
        min_length=1, max_length=20, required=False
    )
    job_type = validate_string_field(
        payload.job_type, "Job type",
        min_length=1, max_length=20, required=False
    )
    job_site = validate_string_field(
        payload.job_site, "Job site",
        min_length=1, max_length=20, required=False
    )
    additional_preferences = validate_string_field(
        payload.additional_preferences, "Additional preferences",
        min_length=0, max_length=2000, required=False
    )
    screening_availability = validate_string_field(
        payload.screening_availability, "Screening availability",
        min_length=0, max_length=255, required=False
    )
    screening_phone = validate_string_field(
        payload.screening_phone, "Screening phone",
        min_length=0, max_length=30, required=False
    )
    job_link = validate_string_field(
        payload.job_link, "Job link",
        min_length=1, max_length=255, required=False
    ) or ""
    duration = validate_string_field(
        payload.duration, "Duration",
        min_length=1, max_length=100, required=False
    )
    short_description = validate_string_field(
        payload.short_description, "Short description",
        min_length=1, max_length=255, required=False
    )

    # Parse datetime fields
    start_date_obj = None
    if payload.start_date:
        try:
            start_date_obj = datetime.fromisoformat(payload.start_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO 8601 format.")

    apply_by_obj = None
    if payload.apply_by:
        try:
            apply_by_obj = datetime.fromisoformat(payload.apply_by.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid apply_by format. Use ISO 8601 format.")

    min_experience_years = validate_integer_field(
        payload.min_experience_years, "Minimum experience years",
        min_value=0, max_value=60, required=False
    )
    openings = validate_integer_field(
        payload.openings, "Openings",
        min_value=1, max_value=100000, required=False
    )
    salary_min = validate_integer_field(
        payload.salary_min, "Salary min",
        min_value=0, max_value=10**9, required=False
    )
    salary_max = validate_integer_field(
        payload.salary_max, "Salary max",
        min_value=0, max_value=10**9, required=False
    )
    variable_min = validate_integer_field(
        payload.variable_min, "Variable min",
        min_value=0, max_value=10**9, required=False
    )
    variable_max = validate_integer_field(
        payload.variable_max, "Variable max",
        min_value=0, max_value=10**9, required=False
    )

    perks_json = None
    if payload.perks is not None:
        if not isinstance(payload.perks, dict):
            raise HTTPException(status_code=400, detail="Perks must be an object")
        try:
            perks_json = json.dumps(payload.perks, ensure_ascii=False)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid perks format")

    non_negotiables_json = None
    if payload.non_negotiables is not None:
        if not isinstance(payload.non_negotiables, list):
            raise HTTPException(status_code=400, detail="Non-negotiables must be a list")
        cleaned = [str(x).strip() for x in payload.non_negotiables if str(x).strip()]
        non_negotiables_json = json.dumps(cleaned, ensure_ascii=False) if cleaned else None

    required_skills_json = None
    if payload.required_skills is not None:
        if not isinstance(payload.required_skills, list):
            raise HTTPException(status_code=400, detail="Required skills must be a list")
        cleaned_skills = [str(x).strip() for x in payload.required_skills if str(x).strip()]
        required_skills_json = json.dumps(cleaned_skills, ensure_ascii=False) if cleaned_skills else None

    # Validate draft_step
    draft_step = payload.draft_step or 1
    if draft_step < 1 or draft_step > 3:
        draft_step = 1

    # Create job object
    job = Job(
        user_id=user_id,
        job_title=title,
        short_description=short_description or None,
        job_description=description,
        location=location or None,
        salary_range=salary_range or None,
        salary_currency=salary_currency or None,
        salary_min=salary_min,
        salary_max=salary_max,
        variable_min=variable_min,
        variable_max=variable_max,
        opportunity_type=(opportunity_type or None),
        min_experience_years=min_experience_years,
        job_type=(job_type or None),
        job_site=(job_site or None),
        openings=openings,
        perks=perks_json,
        non_negotiables=non_negotiables_json,
        required_skills=required_skills_json,
        additional_preferences=additional_preferences or None,
        screening_availability=screening_availability or None,
        screening_phone=screening_phone or None,
        start_date=start_date_obj,
        duration=duration or None,
        apply_by=apply_by_obj,
        job_link=job_link or None,
        status=status,
    )
    
    if status == "draft":
        if payload.draft_data is not None:
            try:
                job.draft_data = json.dumps(payload.draft_data, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error serializing draft_data: {e}")
                raise HTTPException(status_code=400, detail="Invalid draft data format")
        job.draft_step = draft_step

    # Save to database
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating job: {e}")
        raise handle_database_error(e, "creating job")

    # Module 9: store job embedding (best-effort)
    try:
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        if job_text:
            get_or_create_embedding(db, entity_type="job", entity_id=job.id, text=job_text)
    except Exception as e:
        logger.warning(f"Failed to create embedding for job {job.id}: {e}")
        # Don't fail job creation if embedding fails

    return {"success": True, "job": _job_to_public(job)}


@router.get("")
def list_jobs(
    mine: bool = Query(default=False, description="If true and role is recruiter, return only your jobs"),
    status: str | None = Query(default=None, description="active/closed/draft/deleted"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(Job)

    if user.get("role") == "recruiter" and mine:
        q = q.filter(Job.user_id == int(user.get("sub")))

    # Candidates should only ever see active jobs.
    if user.get("role") == "candidate":
        q = q.filter(func.lower(Job.status) == "active")

    status_norm = (status or "").strip().lower()
    # Be forgiving with common pluralization coming from UI labels.
    if status_norm == "drafts":
        status_norm = "draft"
    if status_norm and status_norm != "all":
        q = q.filter(func.lower(Job.status) == status_norm)
    else:
        # Recruiter "All Jobs" should exclude drafts by default.
        if user.get("role") == "recruiter" and mine:
            q = q.filter(func.lower(Job.status).in_(["active", "closed"]))

    # Hide deleted jobs unless explicitly requested via status=deleted.
    if status_norm != "deleted":
        q = q.filter(func.lower(Job.status) != "deleted")

    jobs = q.order_by(Job.created_at.desc()).all()
    items = [_job_to_public(j) for j in jobs]

    return {"success": True, "jobs": items}


@router.get("/{job_id:int}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Validate job_id
    try:
        job_id = validate_integer_field(job_id, "Job ID", min_value=1)
    except HTTPException:
        raise
    
    # Fetch job
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    except Exception as e:
        logger.error(f"Database error fetching job: {e}")
        raise handle_database_error(e, "fetching job")
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=get_error_message("job_not_found")
        )

    # Candidates cannot view drafts/closed jobs.
    if user.get("role") == "candidate" and job.status != "active":
        raise HTTPException(
            status_code=404,
            detail=get_error_message("job_not_found")
        )

    include_draft = user.get("role") == "recruiter" and job.status == "draft"
    return {"success": True, "job": _job_to_public(job, include_draft=include_draft)}


@router.patch("/{job_id:int}")
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="You can only update your own jobs")

    if payload.title is not None:
        job.job_title = payload.title.strip()
    if payload.short_description is not None:
        job.short_description = payload.short_description.strip() if payload.short_description else None
    if payload.description is not None:
        job.job_description = payload.description
    if payload.location is not None:
        job.location = payload.location.strip() if payload.location else None
    if payload.salary_range is not None:
        job.salary_range = payload.salary_range.strip() if payload.salary_range else None
    if payload.salary_currency is not None:
        job.salary_currency = payload.salary_currency.strip() if payload.salary_currency else None
    if payload.salary_min is not None:
        job.salary_min = validate_integer_field(payload.salary_min, "Salary min", min_value=0, max_value=10**9, required=False)
    if payload.salary_max is not None:
        job.salary_max = validate_integer_field(payload.salary_max, "Salary max", min_value=0, max_value=10**9, required=False)
    if payload.variable_min is not None:
        job.variable_min = validate_integer_field(payload.variable_min, "Variable min", min_value=0, max_value=10**9, required=False)
    if payload.variable_max is not None:
        job.variable_max = validate_integer_field(payload.variable_max, "Variable max", min_value=0, max_value=10**9, required=False)
    if payload.opportunity_type is not None:
        job.opportunity_type = payload.opportunity_type.strip() if payload.opportunity_type else None
    if payload.min_experience_years is not None:
        job.min_experience_years = validate_integer_field(payload.min_experience_years, "Minimum experience years", min_value=0, max_value=60, required=False)
    if payload.job_type is not None:
        job.job_type = payload.job_type.strip() if payload.job_type else None
    if payload.job_site is not None:
        job.job_site = payload.job_site.strip() if payload.job_site else None
    if payload.openings is not None:
        job.openings = validate_integer_field(payload.openings, "Openings", min_value=1, max_value=100000, required=False)
    if payload.perks is not None:
        if not isinstance(payload.perks, dict):
            raise HTTPException(status_code=400, detail="Perks must be an object")
        job.perks = json.dumps(payload.perks, ensure_ascii=False)

    if payload.non_negotiables is not None:
        if not isinstance(payload.non_negotiables, list):
            raise HTTPException(status_code=400, detail="Non-negotiables must be a list")
        cleaned = [str(x).strip() for x in payload.non_negotiables if str(x).strip()]
        job.non_negotiables = json.dumps(cleaned, ensure_ascii=False) if cleaned else None
    if payload.required_skills is not None:
        if not isinstance(payload.required_skills, list):
            raise HTTPException(status_code=400, detail="Required skills must be a list")
        cleaned_skills = [str(x).strip() for x in payload.required_skills if str(x).strip()]
        job.required_skills = json.dumps(cleaned_skills, ensure_ascii=False) if cleaned_skills else None
    if payload.additional_preferences is not None:
        job.additional_preferences = payload.additional_preferences.strip() if payload.additional_preferences else None
    if payload.screening_availability is not None:
        job.screening_availability = payload.screening_availability.strip() if payload.screening_availability else None
    if payload.screening_phone is not None:
        job.screening_phone = payload.screening_phone.strip() if payload.screening_phone else None
    if payload.start_date is not None:
        if payload.start_date:
            try:
                job.start_date = datetime.fromisoformat(payload.start_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO 8601 format.")
        else:
            job.start_date = None
    if payload.duration is not None:
        job.duration = payload.duration.strip() if payload.duration else None
    if payload.apply_by is not None:
        if payload.apply_by:
            try:
                job.apply_by = datetime.fromisoformat(payload.apply_by.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="Invalid apply_by format. Use ISO 8601 format.")
        else:
            job.apply_by = None
    if payload.job_link is not None:
        job.job_link = payload.job_link.strip() if payload.job_link else None
    if payload.status is not None:
        s = payload.status.lower()
        if s not in {"active", "draft", "closed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        job.status = s
        # If publishing, clear draft metadata (optional but keeps data clean).
        if s != "draft":
            job.draft_data = None
            job.draft_step = 1

    if payload.draft_step is not None:
        job.draft_step = int(payload.draft_step)
    if payload.draft_data is not None:
        job.draft_data = json.dumps(payload.draft_data, ensure_ascii=False)

    db.add(job)
    db.commit()
    db.refresh(job)

    # Module 9: refresh job embedding after edits (best-effort)
    try:
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        get_or_create_embedding(db, entity_type="job", entity_id=job.id, text=job_text)
    except Exception:
        pass

    return {"success": True, "job": _job_to_public(job)}


@router.delete("/{job_id:int}", status_code=200)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="You can only delete your own jobs")

    # Soft delete: keep applications/candidates so recruiters can still access history.
    try:
        if job.status != "deleted":
            job.status = "deleted"
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Job cannot be deleted due to related records.") from None
    except Exception:
        db.rollback()
        raise

    return {"success": True, "deleted_job_id": job_id}


async def _analyze_and_persist_application(
    *,
    db: Session,
    job: Job,
    candidate: Candidate,
    dest_path: Path,
    rel_path: Path,
    stored_filename: str,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
    progress_task_id: str | None = None,
) -> dict:
    """
    Core apply+analysis pipeline used by both sync and async flows.
    Returns the "application" payload returned to the frontend.
    """

    def prog(p: int, msg: str) -> None:
        if progress_task_id:
            update_task(task_id=progress_task_id, percent=p, message=msg)

    prog(8, "Extracting text…")
    ext = Path(original_filename).suffix.lower()
    extraction = extract_and_clean_resume_text(file_path=dest_path.as_posix(), ext=ext)
    extracted = extraction.get("clean_text") or ""

    prog(28, "Parsing resume sections…")
    structured = parse_resume_text(text=extracted)

    prog(42, "AI: structuring resume…")
    ai_structured, ai_structured_meta = await ai_structure_resume(resume_text=extracted)

    prog(58, "AI: matching resume to job…")
    ai_match, ai_match_meta = await ai_match_resume_to_job(
        job_title=job.job_title,
        job_description=job.job_description,
        resume_text=extracted,
        db=db,
        job_id=job.id,
    )
    ai_error: dict | None = None
    ai_sections: dict | None = None
    ai_overall_match_score: int | None = None
    try:
        if isinstance(ai_match, dict) and isinstance(ai_match.get("overall_match_score"), int):
            ai_overall_match_score = int(ai_match.get("overall_match_score") or 0)
            ai_sections = {
                "education_summary": ai_match.get("education_summary") or {"score": 0, "summary": ""},
                "projects_summary": ai_match.get("projects_summary") or {"score": 0, "summary": ""},
                "work_experience_summary": ai_match.get("work_experience_summary") or {"score": 0, "summary": ""},
            }
    except Exception:
        ai_sections = None
        ai_overall_match_score = None

    # If AI is unavailable (quota/rate limit / overload), show a clear error to UI instead of
    # showing keyword fallback explanations.
    try:
        code = int((ai_match_meta or {}).get("error_code") or 0)
        msg = str((ai_match_meta or {}).get("error_message") or "")
        quota_hit = code == 429 or ("RESOURCE_EXHAUSTED" in msg) or ("Quota exceeded" in msg) or ("rate limit" in msg.lower())
        if quota_hit:
            ai_error = {
                "type": "token_exhausted",
                "message": "Token exhausted (Gemini free-tier quota). Please try again later.",
            }
        else:
            overloaded = code in {408, 500, 502, 503, 504} or ("overloaded" in msg.lower()) or ("unavailable" in msg.lower())
            if overloaded:
                ai_error = {
                    "type": "ai_unavailable",
                    "message": "AI is temporarily unavailable (Gemini overloaded). Please try again later.",
                }
    except Exception:
        ai_error = None
    if ai_error:
        match_score, _fallback_expl = score_resume_against_job(
            job_title=job.job_title,
            job_description=job.job_description,
            resume_text=extracted,
        )
        explanation = ai_error["message"]
    elif ai_match and isinstance(ai_match.get("score"), int):
        score_0_100 = int(ai_match["score"])
        match_score = max(0.0, min(1.0, score_0_100 / 100.0))
        # If we have sectioned output, prefer keeping a short, scan-friendly explanation.
        if ai_sections:
            parts = []
            try:
                parts.append(str((ai_sections.get("education_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("projects_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("work_experience_summary") or {}).get("summary") or "").strip())
            except Exception:
                parts = []
            explanation = " ".join([p for p in parts if p]).strip()
        else:
            explanation = ai_match.get("explanation") or ""
        if not explanation:
            explanation = "AI generated a score but no explanation was provided."
    else:
        match_score, explanation = score_resume_against_job(
            job_title=job.job_title,
            job_description=job.job_description,
            resume_text=extracted,
        )

    prog(72, "Saving resume…")
    semantic_score = 0.0

    prog(84, "Computing semantic similarity…")
    # Create resume record first (needed for embedding caching keyed by resume_id)
    resume = Resume(
        candidate_id=candidate.id,
        file_path=rel_path.as_posix(),
        stored_filename=stored_filename,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        extracted_text=extracted,
        structured_json=json.dumps(structured, ensure_ascii=False),
        structured_version=int(structured.get("version") or 1),
        ai_structured_json=json.dumps(ai_structured, ensure_ascii=False) if ai_structured else None,
        ai_structured_version=int((ai_structured or {}).get("version") or 1) if ai_structured else 1,
        ai_model=(ai_structured_meta.get("model") if isinstance(ai_structured_meta, dict) else None),
        ai_generated_at=datetime.now(timezone.utc) if ai_structured else None,
        ai_warnings=json.dumps(ai_structured_meta.get("warnings", []), ensure_ascii=False)
        if isinstance(ai_structured_meta, dict) and ai_structured_meta.get("warnings")
        else None,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # Compute semantic similarity with embedding cache keys.
    try:
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        semantic_score = resume_job_similarity(
            db,
            resume_id=resume.id,
            job_id=job.id,
            resume_text=extracted,
            job_text=job_text,
        )
    except Exception:
        pass

    prog(90, "Computing final score…")
    ai_rel_pct = None
    try:
        if ai_overall_match_score is not None:
            ai_rel_pct = int(ai_overall_match_score)
        elif ai_match and isinstance(ai_match.get("score"), int):
            ai_rel_pct = int(ai_match.get("score") or 0)
    except Exception:
        ai_rel_pct = None

    skills_score, final_score, breakdown = score_application(
        job_title=job.job_title,
        job_description=job.job_description,
        job_required_skills=_job_required_skills_list(job),
        resume_structured_json=resume.structured_json,
        resume_ai_structured_json=getattr(resume, "ai_structured_json", None),
        semantic_score=float(semantic_score),
        ai_relevance_pct=ai_rel_pct,
    )

    prog(93, "Saving results…")
    application = (
        db.query(Application)
        .filter(Application.job_id == job.id, Application.candidate_id == candidate.id)
        .first()
    )
    created = False
    if not application:
        application = Application(job_id=job.id, candidate_id=candidate.id)
        created = True

    application.resume_id = resume.id
    application.match_score = float(match_score)
    application.ai_explanation = explanation
    application.status = _safe_application_status(db, "submitted")

    application.semantic_score = float(semantic_score or 0.0)
    application.skills_score = float(skills_score or 0.0)
    application.final_score = int(final_score or 0)
    # Include AI section summaries in breakdown (if available) for recruiter explainability.
    if ai_sections:
        breakdown["ai_sections"] = ai_sections
        breakdown["ai_overall_match_score"] = int(ai_overall_match_score or 0)
    application.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
    application.score_updated_at = datetime.now(timezone.utc)

    db.add(application)
    db.commit()
    db.refresh(application)

    prog(99, "Finalizing…")
    return {
        "created": created,
        "application": {
            "id": application.id,
            "job_id": application.job_id,
            "candidate_id": application.candidate_id,
            "resume_id": application.resume_id,
            "match_score": application.match_score,
            "ai_explanation": application.ai_explanation,
            "ai_overall_match_score": int(ai_overall_match_score or 0) if ai_overall_match_score is not None else None,
            "ai_sections": ai_sections,
            "ai_error": ai_error,
            "semantic_score": float(application.semantic_score or 0.0),
            "skills_score": float(application.skills_score or 0.0),
            "final_score": int(application.final_score or 0),
            "score_breakdown": breakdown,
            "status": application.status,
            "created_at": application.created_at.isoformat()
            if isinstance(application.created_at, datetime)
            else application.created_at,
        },
    }


async def _run_apply_task(
    *,
    task_id: str,
    job_id: int,
    user_id: int,
    candidate_id: int,
    dest_path: str,
    rel_path: str,
    stored_filename: str,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        candidate = db.query(Candidate).filter(Candidate.id == int(candidate_id)).first()
        if not job or not candidate:
            raise RuntimeError("Job or candidate not found")

        result = await _analyze_and_persist_application(
            db=db,
            job=job,
            candidate=candidate,
            dest_path=Path(dest_path),
            rel_path=Path(rel_path),
            stored_filename=stored_filename,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            progress_task_id=task_id,
        )
        complete_task(task_id=task_id, result=result.get("application"))
    except Exception as e:
        fail_task(task_id=task_id, error_message=str(e))
    finally:
        db.close()


async def _run_scan_task(
    *,
    task_id: str,
    job_id: int,
    user_id: int,
    candidate_id: int,
    dest_path: str,
    original_filename: str,
) -> None:
    """
    Scan-only: analyze resume vs job (AI + deterministic) without creating an Application.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        candidate = db.query(Candidate).filter(Candidate.id == int(candidate_id)).first()
        if not job or not candidate:
            raise RuntimeError("Job or candidate not found")

        def prog(p: int, msg: str) -> None:
            update_task(task_id=task_id, percent=p, message=msg)

        prog(8, "Extracting text…")
        ext = Path(original_filename).suffix.lower()
        extraction = extract_and_clean_resume_text(file_path=str(dest_path), ext=ext)
        extracted = extraction.get("clean_text") or ""

        prog(28, "Parsing resume…")
        structured = parse_resume_text(text=extracted)

        prog(56, "AI: matching resume to job…")
        ai_match, ai_match_meta = await ai_match_resume_to_job(
            job_title=job.job_title,
            job_description=job.job_description,
            resume_text=extracted,
            db=db,
            job_id=job.id,
        )

        ai_error: dict | None = None
        ai_sections: dict | None = None
        ai_overall_match_score: int | None = None
        try:
            if isinstance(ai_match, dict) and isinstance(ai_match.get("overall_match_score"), int):
                ai_overall_match_score = int(ai_match.get("overall_match_score") or 0)
                ai_sections = {
                    "education_summary": ai_match.get("education_summary") or {"score": 0, "summary": ""},
                    "projects_summary": ai_match.get("projects_summary") or {"score": 0, "summary": ""},
                    "work_experience_summary": ai_match.get("work_experience_summary") or {"score": 0, "summary": ""},
                }
        except Exception:
            ai_sections = None
            ai_overall_match_score = None

        # Detect quota/overload to surface to UI
        try:
            code = int((ai_match_meta or {}).get("error_code") or 0)
            msg = str((ai_match_meta or {}).get("error_message") or "")
            quota_hit = code == 429 or ("RESOURCE_EXHAUSTED" in msg) or ("Quota exceeded" in msg) or ("rate limit" in msg.lower())
            if quota_hit:
                ai_error = {"type": "token_exhausted", "message": "Token exhausted (Gemini free-tier quota). Please try again later."}
            else:
                overloaded = code in {408, 500, 502, 503, 504} or ("overloaded" in msg.lower()) or ("unavailable" in msg.lower())
                if overloaded:
                    ai_error = {"type": "ai_unavailable", "message": "AI is temporarily unavailable (Gemini overloaded). Please try again later."}
        except Exception:
            ai_error = None

        prog(74, "Computing similarity…")
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        semantic_score = fallback_semantic_similarity(resume_text=extracted, job_text=job_text)

        prog(90, "Calculating final score…")
        ai_rel_pct = None
        try:
            if ai_overall_match_score is not None:
                ai_rel_pct = int(ai_overall_match_score)
            elif ai_match and isinstance(ai_match.get("score"), int):
                ai_rel_pct = int(ai_match.get("score") or 0)
        except Exception:
            ai_rel_pct = None

        skills_score, final_score, breakdown = score_application(
            job_title=job.job_title,
            job_description=job.job_description,
            job_required_skills=_job_required_skills_list(job),
            resume_structured_json=json.dumps(structured, ensure_ascii=False),
            resume_ai_structured_json=None,
            semantic_score=float(semantic_score),
            ai_relevance_pct=ai_rel_pct,
        )

        if ai_sections:
            breakdown["ai_sections"] = ai_sections
            breakdown["ai_overall_match_score"] = int(ai_overall_match_score or 0)

        # Build a short explanation for display
        explanation = ""
        if ai_error:
            explanation = ai_error.get("message") or ""
        elif ai_sections:
            parts: list[str] = []
            try:
                parts.append(str((ai_sections.get("education_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("projects_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("work_experience_summary") or {}).get("summary") or "").strip())
            except Exception:
                parts = []
            explanation = " ".join([p for p in parts if p]).strip()
        elif isinstance(ai_match, dict):
            explanation = str(ai_match.get("explanation") or "").strip()

        result = {
            "job_id": int(job.id),
            "match_score": float((ai_overall_match_score or 0) / 100.0) if ai_overall_match_score is not None else float(final_score / 100.0),
            "ai_explanation": explanation or "",
            "ai_error": ai_error,
            "ai_overall_match_score": int(ai_overall_match_score or 0) if ai_overall_match_score is not None else None,
            "ai_sections": ai_sections,
            "semantic_score": float(semantic_score or 0.0),
            "skills_score": float(skills_score or 0.0),
            "final_score": int(final_score or 0),
            "score_breakdown": breakdown,
        }

        complete_task(task_id=task_id, result=result)
    except Exception as e:
        fail_task(task_id=task_id, error_message=str(e))
    finally:
        db.close()
        # Best-effort: delete scan file
        try:
            p = Path(str(dest_path))
            if p.exists():
                p.unlink()
        except Exception:
            pass


@router.post("/{job_id:int}/apply")
async def apply_to_job(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    """
    Candidate flow:
      Candidate opens a job -> uploads resume -> resume is tied to that job application only.

    Creates or updates an Application(job_id, candidate_id) with a newly stored Resume.
    Returns match_score + ai_explanation.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    existing = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if existing:
        return _already_applied_response(existing)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.content_type and file.content_type not in ALLOWED_RESUME_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(UPLOAD_DIR) / "applications" / str(job_id) / str(candidate.id)
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / stored_filename

    rel_path = Path("applications") / str(job_id) / str(candidate.id) / stored_filename

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESUME_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (max 5MB)")
                out.write(chunk)
    except HTTPException:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to store file")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    result = await _analyze_and_persist_application(
        db=db,
        job=job,
        candidate=candidate,
        dest_path=dest,
        rel_path=rel_path,
        stored_filename=stored_filename,
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=size,
        progress_task_id=None,
    )
    return {"success": True, "already_applied": False, **result}


async def _analyze_and_update_existing_application(
    *,
    db: Session,
    application_id: int,
) -> None:
    """
    Re-run analysis/scoring for an existing saved application+resume (no new rows).
    This is used by apply_save to populate AI explanations + scores in the background.
    """
    a = db.query(Application).filter(Application.id == int(application_id)).first()
    if not a or not a.resume_id:
        raise RuntimeError("Application or resume not found")

    job = db.query(Job).filter(Job.id == int(a.job_id)).first()
    resume = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
    if not job or not resume:
        raise RuntimeError("Job or resume not found")

    abs_path = Path(UPLOAD_DIR) / Path(resume.file_path or "")
    if not abs_path.exists():
        raise RuntimeError("Resume file missing on server")

    ext = Path(resume.original_filename or abs_path.name).suffix.lower()
    extraction = extract_and_clean_resume_text(file_path=abs_path.as_posix(), ext=ext)
    extracted = extraction.get("clean_text") or ""

    structured = parse_resume_text(text=extracted)

    ai_structured, ai_structured_meta = await ai_structure_resume(resume_text=extracted)
    ai_match, ai_match_meta = await ai_match_resume_to_job(
        job_title=job.job_title,
        job_description=job.job_description,
        resume_text=extracted,
        db=db,
        job_id=job.id,
        resume_id=resume.id,
    )

    ai_error: dict | None = None
    ai_sections: dict | None = None
    ai_overall_match_score: int | None = None
    try:
        if isinstance(ai_match, dict) and isinstance(ai_match.get("overall_match_score"), int):
            ai_overall_match_score = int(ai_match.get("overall_match_score") or 0)
            ai_sections = {
                "education_summary": ai_match.get("education_summary") or {"score": 0, "summary": ""},
                "projects_summary": ai_match.get("projects_summary") or {"score": 0, "summary": ""},
                "work_experience_summary": ai_match.get("work_experience_summary") or {"score": 0, "summary": ""},
            }
    except Exception:
        ai_sections = None
        ai_overall_match_score = None

    # Detect quota/overload to surface to UI
    try:
        code = int((ai_match_meta or {}).get("error_code") or 0)
        msg = str((ai_match_meta or {}).get("error_message") or "")
        quota_hit = code == 429 or ("RESOURCE_EXHAUSTED" in msg) or ("Quota exceeded" in msg) or ("rate limit" in msg.lower())
        if quota_hit:
            ai_error = {"type": "token_exhausted", "message": "Token exhausted (Gemini free-tier quota). Please try again later."}
        else:
            overloaded = code in {408, 500, 502, 503, 504} or ("overloaded" in msg.lower()) or ("unavailable" in msg.lower())
            if overloaded:
                ai_error = {"type": "ai_unavailable", "message": "AI is temporarily unavailable (Gemini overloaded). Please try again later."}
    except Exception:
        ai_error = None

    if ai_error:
        match_score, _fallback_expl = score_resume_against_job(
            job_title=job.job_title,
            job_description=job.job_description,
            resume_text=extracted,
        )
        explanation = ai_error["message"]
    elif ai_match and isinstance(ai_match.get("score"), int):
        score_0_100 = int(ai_match["score"])
        match_score = max(0.0, min(1.0, score_0_100 / 100.0))
        if ai_sections:
            parts: list[str] = []
            try:
                parts.append(str((ai_sections.get("education_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("projects_summary") or {}).get("summary") or "").strip())
                parts.append(str((ai_sections.get("work_experience_summary") or {}).get("summary") or "").strip())
            except Exception:
                parts = []
            explanation = " ".join([p for p in parts if p]).strip()
        else:
            explanation = ai_match.get("explanation") or ""
        if not explanation:
            explanation = "AI generated a score but no explanation was provided."
    else:
        match_score, explanation = score_resume_against_job(
            job_title=job.job_title,
            job_description=job.job_description,
            resume_text=extracted,
        )

    # Update existing resume row
    resume.extracted_text = extracted
    resume.structured_json = json.dumps(structured, ensure_ascii=False)
    resume.structured_version = int(structured.get("version") or 1)
    resume.ai_structured_json = json.dumps(ai_structured, ensure_ascii=False) if ai_structured else None
    resume.ai_structured_version = int((ai_structured or {}).get("version") or 1) if ai_structured else 1
    resume.ai_model = (ai_structured_meta.get("model") if isinstance(ai_structured_meta, dict) else None)
    resume.ai_generated_at = datetime.now(timezone.utc) if ai_structured else None
    resume.ai_warnings = (
        json.dumps(ai_structured_meta.get("warnings", []), ensure_ascii=False)
        if isinstance(ai_structured_meta, dict) and ai_structured_meta.get("warnings")
        else None
    )

    # Compute semantic similarity + final score
    semantic_score = 0.0
    try:
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        semantic_score = resume_job_similarity(
            db,
            resume_id=resume.id,
            job_id=job.id,
            resume_text=extracted,
            job_text=job_text,
        )
    except Exception:
        semantic_score = 0.0

    ai_rel_pct = None
    try:
        if ai_overall_match_score is not None:
            ai_rel_pct = int(ai_overall_match_score)
        elif ai_match and isinstance(ai_match.get("score"), int):
            ai_rel_pct = int(ai_match.get("score") or 0)
    except Exception:
        ai_rel_pct = None

    skills_score, final_score, breakdown = score_application(
        job_title=job.job_title,
        job_description=job.job_description,
        job_required_skills=_job_required_skills_list(job),
        resume_structured_json=resume.structured_json,
        resume_ai_structured_json=getattr(resume, "ai_structured_json", None),
        semantic_score=float(semantic_score),
        ai_relevance_pct=ai_rel_pct,
    )
    if ai_sections:
        breakdown["ai_sections"] = ai_sections
        breakdown["ai_overall_match_score"] = int(ai_overall_match_score or 0)

    a.match_score = float(match_score)
    a.ai_explanation = explanation
    a.status = _safe_application_status(db, "submitted")
    a.semantic_score = float(semantic_score or 0.0)
    a.skills_score = float(skills_score or 0.0)
    a.final_score = int(final_score or 0)
    a.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
    a.score_updated_at = datetime.now(timezone.utc)

    db.add(resume)
    db.add(a)
    db.commit()


async def _run_apply_save_analysis_task(*, application_id: int) -> None:
    db = SessionLocal()
    try:
        logger = logging.getLogger(__name__)
        logger.info("apply_save analysis start application_id=%s", application_id)
        await _analyze_and_update_existing_application(db=db, application_id=int(application_id))
        logger.info("apply_save analysis done application_id=%s", application_id)
    except Exception as e:
        try:
            a = db.query(Application).filter(Application.id == int(application_id)).first()
            if a:
                a.ai_explanation = f"Analysis failed: {str(e)}"
                a.final_score = int(a.final_score or 0)
                a.score_breakdown_json = json.dumps(
                    {"error": "analysis_failed", "message": str(e)},
                    ensure_ascii=False,
                )
                a.score_updated_at = datetime.now(timezone.utc)
                a.status = _safe_application_status(db, "submitted")
                db.add(a)
                db.commit()
            logger.exception("apply_save analysis failed application_id=%s", application_id)
        except Exception:
            db.rollback()
    finally:
        db.close()


@router.post("/{job_id:int}/apply_save")
async def apply_save_only(
    job_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    """
    Apply-only (no analysis/scoring):
    - Creates (or updates) Application(job_id, candidate_id)
    - Optionally stores uploaded resume file and links Resume -> application.resume_id
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    existing = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if existing:
        return _already_applied_response(existing)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.content_type and file.content_type not in ALLOWED_RESUME_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(UPLOAD_DIR) / "applications" / str(job_id) / str(candidate.id)
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / stored_filename
    rel_path = Path("applications") / str(job_id) / str(candidate.id) / stored_filename

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESUME_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (max 5MB)")
                out.write(chunk)
    except HTTPException:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to store file")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    # Save Resume row (no extracted_text/analysis here).
    resume = Resume(
        candidate_id=candidate.id,
        file_path=rel_path.as_posix(),
        stored_filename=stored_filename,
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=size,
        extracted_text=None,
        structured_json=None,
        ai_structured_json=None,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    resume_id = int(resume.id)

    application = (
        db.query(Application)
        .filter(Application.job_id == job.id, Application.candidate_id == candidate.id)
        .first()
    )
    created = False
    if not application:
        application = Application(job_id=job.id, candidate_id=candidate.id)
        created = True

    application.resume_id = int(resume_id)
    application.status = _safe_application_status(db, "submitted")
    db.add(application)
    db.commit()
    db.refresh(application)

    # Fire-and-forget: populate scores + AI explanations in the background so
    # "View Details" can show them shortly after saving.
    try:
        background_tasks.add_task(_run_apply_save_analysis_task, application_id=int(application.id))
    except Exception:
        pass

    return {
        "success": True,
        "already_applied": False,
        "created": created,
        "application": {
            "id": application.id,
            "job_id": application.job_id,
            "candidate_id": application.candidate_id,
            "resume_id": application.resume_id,
            "status": application.status,
            "created_at": application.created_at.isoformat()
            if isinstance(application.created_at, datetime)
            else application.created_at,
        },
        "job": _job_to_public(job),
    }


@router.post("/{job_id:int}/apply_async")
async def apply_to_job_async(
    job_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    """
    Async candidate flow:
      - Returns a task_id immediately
      - Client polls /jobs/apply_status/{task_id} for percent + final result
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    existing = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if existing:
        return _already_applied_response(existing)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.content_type and file.content_type not in ALLOWED_RESUME_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(UPLOAD_DIR) / "applications" / str(job_id) / str(candidate.id)
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / stored_filename

    rel_path = Path("applications") / str(job_id) / str(candidate.id) / stored_filename

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESUME_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (max 5MB)")
                out.write(chunk)
    except HTTPException:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to store file")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    task_id = uuid4().hex
    create_task(task_id=task_id, user_id=int(user.get("sub")), job_id=int(job_id))
    update_task(task_id=task_id, percent=3, message="Uploaded. Starting analysis…")

    background_tasks.add_task(
        _run_apply_task,
        task_id=task_id,
        job_id=int(job_id),
        user_id=int(user.get("sub")),
        candidate_id=int(candidate.id),
        dest_path=dest.as_posix(),
        rel_path=rel_path.as_posix(),
        stored_filename=stored_filename,
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=int(size),
    )

    return {"success": True, "already_applied": False, "task_id": task_id}


@router.post("/{job_id:int}/scan_resume_async")
async def scan_resume_async(
    job_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    """
    Scan-only (no application saved):
      - Returns a task_id immediately
      - Client polls /jobs/apply_status/{task_id} for percent + scan result
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.content_type and file.content_type not in ALLOWED_RESUME_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))

    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(UPLOAD_DIR) / "scans" / str(job_id) / str(candidate.id)
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / stored_filename

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESUME_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (max 5MB)")
                out.write(chunk)
    except HTTPException:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to store file")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    task_id = uuid4().hex
    create_task(task_id=task_id, user_id=int(user.get("sub")), job_id=int(job_id))
    update_task(task_id=task_id, percent=3, message="Uploaded. Starting scan…")

    background_tasks.add_task(
        _run_scan_task,
        task_id=task_id,
        job_id=int(job_id),
        user_id=int(user.get("sub")),
        candidate_id=int(candidate.id),
        dest_path=dest.as_posix(),
        original_filename=original_filename,
    )

    return {"success": True, "task_id": task_id}


@router.get("/applied")
def list_applied_jobs(
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    apps = (
        db.query(Application)
        .filter(Application.candidate_id == candidate.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    items: list[dict] = []
    for a in apps:
        job = a.job
        items.append(
            {
                "application_id": a.id,
                "job": _job_to_public(job) if job else None,
                "status": a.status,
                "created_at": a.created_at.isoformat() if isinstance(a.created_at, datetime) else a.created_at,
                "final_score": int(a.final_score or 0),
            }
        )
    return {"success": True, "applications": items}


@router.get("/{job_id:int}/my_application")
def my_application_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    application = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if not application:
        return {"success": True, "already_applied": False, "application": None}
    return _already_applied_response(application)


@router.get("/applications/{application_id}")
def application_details(
    application_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    a = (
        db.query(Application)
        .filter(Application.id == int(application_id), Application.candidate_id == candidate.id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    job = a.job
    breakdown = None
    ai_sections = None
    ai_overall = None
    try:
        breakdown = json.loads(a.score_breakdown_json) if a.score_breakdown_json else None
        if isinstance(breakdown, dict):
            ai_sections = breakdown.get("ai_sections")
            ai_overall = breakdown.get("ai_overall_match_score")
    except Exception:
        breakdown = None
    resume_meta = None
    try:
        if a.resume_id:
            r = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
            if r and r.candidate_id == candidate.id:
                resume_meta = {
                    "id": int(r.id),
                    "original_filename": r.original_filename,
                    "content_type": r.content_type,
                    "size_bytes": int(r.size_bytes or 0),
                }
    except Exception:
        resume_meta = None

    return {
        "success": True,
        "application": {
            "id": a.id,
            "job_id": a.job_id,
            "resume_id": a.resume_id,
            "status": a.status,
            "created_at": a.created_at.isoformat() if isinstance(a.created_at, datetime) else a.created_at,
            "score_updated_at": a.score_updated_at.isoformat()
            if isinstance(getattr(a, "score_updated_at", None), datetime)
            else getattr(a, "score_updated_at", None),
            "match_score": float(a.match_score or 0.0),
            "ai_explanation": a.ai_explanation,
            "ai_sections": ai_sections,
            "ai_overall_match_score": int(ai_overall or 0) if ai_overall is not None else None,
            "semantic_score": float(a.semantic_score or 0.0),
            "skills_score": float(a.skills_score or 0.0),
            "final_score": int(a.final_score or 0),
            "score_breakdown": breakdown,
            "job": _job_to_public(job) if job else None,
            "resume": resume_meta,
        },
    }


def _application_details_payload(*, db: Session, a: Application, candidate: Candidate | None) -> dict:
    job = a.job
    breakdown = None
    ai_sections = None
    ai_overall = None
    try:
        breakdown = json.loads(a.score_breakdown_json) if a.score_breakdown_json else None
        if isinstance(breakdown, dict):
            ai_sections = breakdown.get("ai_sections")
            ai_overall = breakdown.get("ai_overall_match_score")
    except Exception:
        breakdown = None

    resume_meta = None
    try:
        if a.resume_id:
            r = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
            if r and ((candidate and r.candidate_id == candidate.id) or (not candidate)):
                resume_meta = {
                    "id": int(r.id),
                    "original_filename": r.original_filename,
                    "content_type": r.content_type,
                    "size_bytes": int(r.size_bytes or 0),
                }
    except Exception:
        resume_meta = None

    return {
        "id": a.id,
        "job_id": a.job_id,
        "resume_id": a.resume_id,
        "status": a.status,
        "created_at": a.created_at.isoformat() if isinstance(a.created_at, datetime) else a.created_at,
        "score_updated_at": a.score_updated_at.isoformat()
        if isinstance(getattr(a, "score_updated_at", None), datetime)
        else getattr(a, "score_updated_at", None),
        "match_score": float(a.match_score or 0.0),
        "ai_explanation": a.ai_explanation,
        "ai_sections": ai_sections,
        "ai_overall_match_score": int(ai_overall or 0) if ai_overall is not None else None,
        "semantic_score": float(a.semantic_score or 0.0),
        "skills_score": float(a.skills_score or 0.0),
        "final_score": int(a.final_score or 0),
        "score_breakdown": breakdown,
        "job": _job_to_public(job) if job else None,
        "resume": resume_meta,
    }


@router.get("/applications/{application_id}/shared")
def application_details_shared(
    application_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Shared view for both candidate and recruiter:
    - Candidate: must own the application
    - Recruiter: must own the job tied to the application
    """
    a = db.query(Application).filter(Application.id == int(application_id)).first()
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")

    role = user.get("role")
    if role == "candidate":
        candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
        if int(a.candidate_id or 0) != int(candidate.id):
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"success": True, "application": _application_details_payload(db=db, a=a, candidate=candidate)}

    if role == "recruiter":
        job = a.job
        if not job or int(job.user_id or 0) != int(user.get("sub")):
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"success": True, "application": _application_details_payload(db=db, a=a, candidate=None)}

    raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/applications/{application_id}/resume")
def download_application_resume(
    application_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Stream the resume file for an application (shared candidate+recruiter auth).
    """
    a = db.query(Application).filter(Application.id == int(application_id)).first()
    if not a or not a.resume_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    role = user.get("role")
    if role == "candidate":
        candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
        if int(a.candidate_id or 0) != int(candidate.id):
            raise HTTPException(status_code=403, detail="Forbidden")
        resume = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
        if not resume or int(resume.candidate_id or 0) != int(candidate.id):
            raise HTTPException(status_code=404, detail="Resume not found")
    elif role == "recruiter":
        job = a.job
        if not job or int(job.user_id or 0) != int(user.get("sub")):
            raise HTTPException(status_code=403, detail="Forbidden")
        resume = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    abs_path = Path(UPLOAD_DIR) / Path(resume.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")

    return FileResponse(
        abs_path,
        media_type=resume.content_type or "application/octet-stream",
        filename=resume.original_filename,
    )


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    a = db.query(Application).filter(Application.id == int(application_id)).first()
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == int(a.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Authorization: Allow recruiters to delete applications from their jobs OR candidates to withdraw their own applications
    user_role = user.get("role")
    user_id = int(user.get("sub"))
    
    if user_role == "recruiter":
        if job.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only delete applications for your own jobs")
    elif user_role == "candidate":
        # Get candidate using the same method as other candidate endpoints
        candidate = _find_or_create_candidate(db, user_id=user_id)
        if a.candidate_id != candidate.id:
            raise HTTPException(status_code=403, detail="You can only withdraw your own applications")
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resume_id = a.resume_id
    job_id = a.job_id
    try:
        # Remove dependent interviews
        db.query(Interview).filter(Interview.application_id == int(a.id)).delete(synchronize_session=False)
        db.delete(a)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Best-effort: delete resume + embeddings created for this application
    try:
        if resume_id:
            db.query(Embedding).filter(Embedding.entity_type == "resume", Embedding.entity_id == int(resume_id)).delete(synchronize_session=False)
            r = db.query(Resume).filter(Resume.id == int(resume_id)).first()
            if r:
                # delete file
                try:
                    p = Path(UPLOAD_DIR) / (r.file_path or "")
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
                db.delete(r)
                db.commit()
    except Exception:
        db.rollback()

    return {"success": True, "deleted_application_id": int(application_id), "job_id": int(job_id)}


@router.get("/apply_status/{task_id}")
def apply_status(
    task_id: str,
    user=Depends(candidate_only),
):
    t = get_task(task_id=task_id)
    if not t or int(t.get("user_id") or 0) != int(user.get("sub")):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": public_view(t)}


@router.get("/{job_id:int}/ranked_candidates")
def ranked_candidates(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="You can only view candidates for your own jobs")

    apps = (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(
            func.coalesce(Application.final_score, -1).desc(),
            func.coalesce(Application.semantic_score, -1).desc(),
            Application.created_at.desc(),
        )
        .all()
    )

    items: list[dict] = []
    for a in apps:
        cand = a.candidate
        breakdown = None
        try:
            breakdown = json.loads(a.score_breakdown_json) if a.score_breakdown_json else None
        except Exception:
            breakdown = None
        items.append(
            {
                "application_id": a.id,
                "job_id": a.job_id,
                "candidate": {
                    "id": cand.id if cand else None,
                    "name": cand.name if cand else None,
                    "email": cand.email if cand else None,
                },
                "resume_id": a.resume_id,
                "semantic_score": float(a.semantic_score or 0.0),
                "skills_score": float(a.skills_score or 0.0),
                "final_score": int(a.final_score or 0),
                "breakdown": breakdown,
                "status": a.status,
                "created_at": a.created_at.isoformat() if isinstance(a.created_at, datetime) else a.created_at,
            }
        )

    return {"success": True, "job": _job_to_public(job), "candidates": items}


@router.get("/{job_id:int}/semantic_match/{resume_id:int}")
def semantic_match(
    job_id: int,
    resume_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Ensure this resume belongs to the logged-in candidate
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    if resume.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Resume not found")

    job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
    score = resume_job_similarity(
        db,
        resume_id=resume.id,
        job_id=job.id,
        resume_text=resume.extracted_text or "",
        job_text=job_text,
    )

    return {"success": True, "semantic_score": float(score)}
