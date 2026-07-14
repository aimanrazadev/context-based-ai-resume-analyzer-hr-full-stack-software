from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import SessionLocal, get_db
from ..models.application import Application
from ..models.candidate import Candidate
from ..models.embedding import Embedding
from ..models.job import Job
from ..models.resume import Resume
from ..models.user import User
from ..services.resume_extractor import extract_and_clean_resume_text
from ..services.resume_parser import parse_resume_text
from ..services.ai_service import analyze_resume_for_job
from ..services.application_service import (
    ai_analysis_payload,
    analysis_conflicts_with_skill_snapshot,
    classify_required_skills_from_text,
    classify_required_skills_from_resume,
    delete_ai_resume_analysis,
    deterministic_insights_from_resume,
    factual_candidate_summary_from_resume,
    is_evaluative_candidate_summary,
    upsert_ai_resume_analysis,
)
from ..modules.matching.skills import normalize_required_skills
from ..modules.resumes.storage import (
    build_resume_storage_path,
    copy_scan_to_application_storage,
    safe_unlink,
    save_upload_file,
    validate_resume_upload,
)
from ..services.embedding_service import embed_text, get_or_create_embedding
from ..services.similarity import cosine_similarity
from ..services.matching_pipeline import evaluate_candidate_for_job
from ..services.progress_tracker import complete_task, create_task, fail_task, get_task, public_view, update_task
from ..modules.applications.status import (
    ALLOWED_APPLICATION_STATUSES,
    normalize_application_status,
)
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
from ..utils.json_utils import safe_json_loads

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
    perks_payload = safe_json_loads(getattr(job, "perks", None))
    non_negotiables_payload = safe_json_loads(getattr(job, "non_negotiables", None))
    required_skills_payload = safe_json_loads(getattr(job, "required_skills", None))
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
        payload["draft_data"] = safe_json_loads(job.draft_data)
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
    start_date: str | None = None  # ISO datetime string
    duration: str | None = Field(default=None, max_length=100)
    apply_by: str | None = None  # ISO datetime string
    job_link: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None)  # active/draft/closed
    draft_data: dict | None = None
    draft_step: int | None = Field(default=None, ge=1, le=3)


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=50)


class ApplyFromScanRequest(BaseModel):
    task_id: str = Field(..., min_length=8, max_length=120)


def _normalize_application_status(status: str | None) -> str:
    return normalize_application_status(status)


def _create_job_embedding_background(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        if not job:
            return
        job_text = "\n".join(
            str(part or "")
            for part in (
                job.job_title,
                getattr(job, "short_description", None),
                job.job_description,
                getattr(job, "required_skills", None),
                getattr(job, "non_negotiables", None),
            )
            if str(part or "").strip()
        ).strip()
        if job_text:
            get_or_create_embedding(db, entity_type="job", entity_id=job.id, text=job_text)
    except Exception as e:
        logger.warning(f"Failed to create embedding for job {job_id}: {e}")
    finally:
        db.close()


def _find_or_create_candidate(db: Session, *, user_id: int) -> Candidate:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    candidate = db.query(Candidate).filter(Candidate.user_id == user.id).first()
    if not candidate and user.email:
        candidate = db.query(Candidate).filter(Candidate.email == user.email).first()
    if candidate:
        if candidate.user_id is None:
            candidate.user_id = user.id
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
        return candidate

    name = user.name or (user.email.split("@", 1)[0] if user.email else "Candidate")
    candidate = Candidate(name=name, email=user.email, user_id=user.id)
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
    result = normalize_required_skills(getattr(job, "required_skills", None))
    return result or None


def parse_optional_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format. Use ISO 8601 format.")


def _serialize_string_list(value: list[str] | None, field_label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail=f"{field_label} must be a list")
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def serialize_job_json_fields(payload: JobCreate | JobUpdate) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    if payload.perks is not None:
        if not isinstance(payload.perks, dict):
            raise HTTPException(status_code=400, detail="Perks must be an object")
        values["perks"] = json.dumps(payload.perks, ensure_ascii=False)
    if payload.non_negotiables is not None:
        values["non_negotiables"] = _serialize_string_list(payload.non_negotiables, "Non-negotiables")
    if payload.required_skills is not None:
        values["required_skills"] = _serialize_string_list(payload.required_skills, "Required skills")
    if payload.draft_data is not None:
        values["draft_data"] = json.dumps(payload.draft_data, ensure_ascii=False)
    return values


def _extraction_metadata(extraction: dict) -> dict:
    return {
        key: value
        for key, value in extraction.items()
        if key not in {"raw_text", "clean_text"}
    }


def _validated_extracted_text(extraction: dict) -> str:
    text_value = str(extraction.get("clean_text") or "").strip()
    if extraction.get("extraction_status") == "failed" or not text_value:
        raise HTTPException(
            status_code=422,
            detail=str(extraction.get("error_message") or "Could not read resume. Please upload a valid PDF or DOCX."),
        )
    return text_value


def _already_applied_response(application: Application) -> dict:
    return {
        "success": True,
        "already_applied": True,
        "application": _application_brief_payload(application),
    }


@router.post("", status_code=201)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
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

    start_date_obj = parse_optional_datetime(payload.start_date, "start_date")
    apply_by_obj = parse_optional_datetime(payload.apply_by, "apply_by")

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

    json_fields = serialize_job_json_fields(payload)

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
        perks=json_fields.get("perks"),
        non_negotiables=json_fields.get("non_negotiables"),
        required_skills=json_fields.get("required_skills"),
        additional_preferences=additional_preferences or None,
        start_date=start_date_obj,
        duration=duration or None,
        apply_by=apply_by_obj,
        job_link=job_link or None,
        status=status,
    )
    
    if status == "draft":
        if "draft_data" in json_fields:
            job.draft_data = json_fields.get("draft_data")
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

    # Module 9: store job embedding best-effort after responding so the recruiter UI
    # is not blocked by local model loading or embedding generation.
    background_tasks.add_task(_create_job_embedding_background, int(job.id))

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

    json_fields = serialize_job_json_fields(payload)
    if "perks" in json_fields:
        job.perks = json_fields.get("perks")
    if "non_negotiables" in json_fields:
        job.non_negotiables = json_fields.get("non_negotiables")
    if "required_skills" in json_fields:
        job.required_skills = json_fields.get("required_skills")
    if payload.additional_preferences is not None:
        job.additional_preferences = payload.additional_preferences.strip() if payload.additional_preferences else None
    if payload.start_date is not None:
        job.start_date = parse_optional_datetime(payload.start_date, "start_date")
    if payload.duration is not None:
        job.duration = payload.duration.strip() if payload.duration else None
    if payload.apply_by is not None:
        job.apply_by = parse_optional_datetime(payload.apply_by, "apply_by")
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
    if "draft_data" in json_fields:
        job.draft_data = json_fields.get("draft_data")

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




async def _run_scan_task(
    *,
    task_id: str,
    job_id: int,
    user_id: int,
    candidate_id: int,
    dest_path: str,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
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

        prog(8, "Extracting text...")
        ext = Path(original_filename).suffix.lower()
        extraction = extract_and_clean_resume_text(file_path=str(dest_path), ext=ext)
        extracted = _validated_extracted_text(extraction)

        prog(28, "Parsing resume...")
        structured = parse_resume_text(text=extracted)

        prog(74, "Computing similarity...")
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        try:
            semantic_score = cosine_similarity(embed_text(extracted), embed_text(job_text))
        except Exception:
            semantic_score = 0.0

        prog(90, "Calculating final score...")
        required_skills = _job_required_skills_list(job) or []
        live_snapshot = classify_required_skills_from_text(
            text=f"{extracted}\n{json.dumps(structured, ensure_ascii=False)}",
            required_skills=required_skills,
        )
        live_matched = live_snapshot.get("matched_skills") or []
        live_missing = live_snapshot.get("missing_skills") or []
        ai_analysis, ai_meta = await analyze_resume_for_job(
            structured_resume=structured,
            resume_text=extracted,
            job_title=job.job_title or "",
            job_description=job.job_description or "",
            required_skills=required_skills,
            matched_skills=live_matched,
            missing_skills=live_missing,
        )
        match_result = evaluate_candidate_for_job(
            job_title=job.job_title,
            job_description=job.job_description,
            job_required_skills=required_skills,
            resume_structured_json=json.dumps(structured, ensure_ascii=False),
            resume_ai_structured_json=None,
            semantic_score=float(semantic_score),
            ai_recommendation=str(ai_analysis.get("recommendation") or "Review Manually"),
        )
        skills_score = match_result.skills_score
        final_score = match_result.final_score
        breakdown = match_result.breakdown
        breakdown["matched_skills"] = live_matched
        breakdown["missing_skills"] = live_missing
        ai_analysis["matched_skills"] = live_matched
        ai_analysis["missing_skills"] = live_missing
        explanation = str(ai_analysis.get("reasoning") or ai_analysis.get("candidate_summary") or "")
        ai_error = None if ai_meta.get("status") == "success" else {
            "type": "ai_unavailable",
            "message": ai_meta.get("error_message") or "AI explanation could not be generated. The match score is still available.",
        }

        result = {
            "job_id": int(job.id),
            "ai_explanation": explanation or "",
            "ai_error": ai_error,
            "ai_analysis": ai_analysis,
            "semantic_score": round(float(semantic_score or 0.0) * 100.0, 2),
            "skills_score": float(skills_score or 0.0),
            "final_score": int(final_score or 0),
            "score_breakdown": breakdown,
            "_internal": {
                "scan_file_path": str(dest_path),
                "original_filename": original_filename,
                "content_type": content_type,
                "size_bytes": int(size_bytes or 0),
                "extraction": extraction,
                "structured": structured,
                "ai_meta": ai_meta,
            },
        }

        complete_task(task_id=task_id, result=result)
    except Exception as e:
        fail_task(task_id=task_id, error_message=str(e))
    finally:
        db.close()




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

    original_filename, ext = validate_resume_upload(
        file,
        allowed_extensions=ALLOWED_RESUME_EXTENSIONS,
        allowed_content_types=ALLOWED_RESUME_CONTENT_TYPES,
    )

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    dest, _stored_filename = build_resume_storage_path(
        upload_dir=UPLOAD_DIR,
        bucket="scans",
        job_id=int(job_id),
        candidate_id=int(candidate.id),
        ext=ext,
    )
    size = await save_upload_file(file, dest, max_bytes=MAX_RESUME_BYTES)

    task_id = uuid4().hex
    create_task(task_id=task_id, user_id=int(user.get("sub")), job_id=int(job_id))
    update_task(task_id=task_id, percent=3, message="Uploaded. Starting scan...")

    background_tasks.add_task(
        _run_scan_task,
        task_id=task_id,
        job_id=int(job_id),
        user_id=int(user.get("sub")),
        candidate_id=int(candidate.id),
        dest_path=dest.as_posix(),
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=int(size),
    )

    return {"success": True, "task_id": task_id}


@router.post("/{job_id:int}/apply_from_scan")
async def apply_from_scan(
    job_id: int,
    payload: ApplyFromScanRequest,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    """
    Save the exact completed scan result as the candidate's application.
    This keeps scan, score, AI insights, and application details in one flow.
    """
    job = db.query(Job).filter(Job.id == int(job_id)).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    existing = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if existing:
        return _already_applied_response(existing)

    task = get_task(task_id=payload.task_id)
    if (
        not task
        or int(task.get("user_id") or 0) != int(user.get("sub"))
        or int(task.get("job_id") or 0) != int(job_id)
        or task.get("status") != "done"
    ):
        raise HTTPException(status_code=404, detail="Completed scan not found. Please scan your resume again.")

    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    internal = result.get("_internal") if isinstance(result.get("_internal"), dict) else {}
    scan_file = Path(str(internal.get("scan_file_path") or ""))
    if not scan_file.exists():
        raise HTTPException(status_code=410, detail="Scanned resume expired. Please scan your resume again.")

    original_filename = Path(str(internal.get("original_filename") or scan_file.name)).name
    ext = Path(original_filename).suffix.lower() or scan_file.suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    dest, rel_path, stored_filename = copy_scan_to_application_storage(
        scan_file=scan_file,
        upload_dir=UPLOAD_DIR,
        job_id=int(job_id),
        candidate_id=int(candidate.id),
        original_filename=original_filename,
    )

    extraction = internal.get("extraction") if isinstance(internal.get("extraction"), dict) else {}
    structured = internal.get("structured") if isinstance(internal.get("structured"), dict) else {}
    ai_meta = internal.get("ai_meta") if isinstance(internal.get("ai_meta"), dict) else {}
    ai_analysis = result.get("ai_analysis") if isinstance(result.get("ai_analysis"), dict) else {}
    breakdown = result.get("score_breakdown") if isinstance(result.get("score_breakdown"), dict) else {}

    try:
        resume = Resume(
            candidate_id=candidate.id,
            file_path=rel_path.as_posix(),
            stored_filename=stored_filename,
            original_filename=original_filename,
            content_type=internal.get("content_type"),
            size_bytes=int(internal.get("size_bytes") or 0),
            raw_extracted_text=extraction.get("raw_text") or "",
            extracted_text=extraction.get("clean_text") or "",
            extraction_status=str(extraction.get("extraction_status") or "success"),
            extraction_metadata_json=json.dumps(_extraction_metadata(extraction), ensure_ascii=False),
            structured_json=json.dumps(structured, ensure_ascii=False),
            structured_version=int(structured.get("version") or 1),
            ai_structured_json=None,
            ai_structured_version=1,
            ai_model=str(ai_meta.get("model") or "") or None,
            ai_generated_at=datetime.now(timezone.utc) if ai_analysis else None,
            ai_warnings=json.dumps(ai_meta.get("warnings", []), ensure_ascii=False)
            if isinstance(ai_meta.get("warnings"), list)
            else None,
        )
        db.add(resume)
        db.flush()

        application = Application(job_id=job.id, candidate_id=candidate.id)
        application.resume_id = int(resume.id)
        application.ai_explanation = str(result.get("ai_explanation") or ai_analysis.get("reasoning") or "")
        application.status = normalize_application_status(None)
        application.semantic_score = float(result.get("semantic_score") or 0.0)
        application.skills_score = float(result.get("skills_score") or 0.0)
        application.experience_score = float(breakdown.get("experience_score") or 0.0)
        application.ai_score = float(breakdown.get("ai_score") or 0.0)
        application.final_score = int(result.get("final_score") or 0)
        application.matched_skills_json = json.dumps(ai_analysis.get("matched_skills") or breakdown.get("matched_skills") or [], ensure_ascii=False)
        application.missing_skills_json = json.dumps(ai_analysis.get("missing_skills") or breakdown.get("missing_skills") or [], ensure_ascii=False)
        application.ranking_explanation = application.ai_explanation
        application.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
        application.score_updated_at = datetime.now(timezone.utc)
        db.add(application)
        db.flush()

        upsert_ai_resume_analysis(
            db,
            application_id=int(application.id),
            analysis=ai_analysis,
            metadata=ai_meta or {"status": "success"},
        )
        db.commit()
        db.refresh(application)
    except IntegrityError:
        db.rollback()
        safe_unlink(dest)
        existing = _find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
        if existing:
            return _already_applied_response(existing)
        raise HTTPException(status_code=409, detail="Application already exists") from None
    except Exception:
        db.rollback()
        safe_unlink(dest)
        raise

    safe_unlink(scan_file)

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
            "created_at": application.created_at.isoformat()
            if isinstance(application.created_at, datetime)
            else application.created_at,
        },
        "job": _job_to_public(job),
    }


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


def _application_details_payload(*, db: Session, a: Application, candidate: Candidate | None) -> dict:
    job = a.job
    breakdown = None
    try:
        breakdown = json.loads(a.score_breakdown_json) if a.score_breakdown_json else None
    except Exception:
        breakdown = None

    resume_meta = None
    resume_row = None
    try:
        if a.resume_id:
            r = db.query(Resume).filter(Resume.id == int(a.resume_id)).first()
            if r and ((candidate and r.candidate_id == candidate.id) or (not candidate)):
                resume_row = r
                resume_meta = {
                    "id": int(r.id),
                    "original_filename": r.original_filename,
                    "content_type": r.content_type,
                    "size_bytes": int(r.size_bytes or 0),
                }
    except Exception:
        resume_meta = None

    analysis = ai_analysis_payload(db, application_id=int(a.id))
    if not isinstance(analysis, dict):
        analysis = {}

    required_skills = _job_required_skills_list(job) if job else []
    live_skill_snapshot = classify_required_skills_from_resume(resume_row, required_skills)
    live_matched = live_skill_snapshot.get("matched_skills") or []
    live_missing = live_skill_snapshot.get("missing_skills") or []
    deterministic = deterministic_insights_from_resume(
        resume_row,
        matched_skills=live_matched,
        missing_skills=live_missing,
    )

    if is_evaluative_candidate_summary(analysis.get("candidate_summary")) or not str(analysis.get("candidate_summary") or "").strip():
        analysis["candidate_summary"] = deterministic.get("candidate_summary") or factual_candidate_summary_from_resume(resume_row)
    if not (isinstance(analysis.get("strengths"), list) and analysis.get("strengths")):
        analysis["strengths"] = deterministic.get("strengths") or []
    weakness_conflict = analysis_conflicts_with_skill_snapshot(analysis, live_matched)
    if weakness_conflict or not (isinstance(analysis.get("weaknesses"), list) and analysis.get("weaknesses")):
        analysis["weaknesses"] = deterministic.get("weaknesses") or []
    if not str(analysis.get("strength_reasoning") or "").strip():
        analysis["strength_reasoning"] = deterministic.get("strength_reasoning") or ""
    if weakness_conflict or not str(analysis.get("weakness_reasoning") or "").strip():
        analysis["weakness_reasoning"] = deterministic.get("weakness_reasoning") or ""
    if not str(analysis.get("reasoning") or "").strip():
        analysis["reasoning"] = deterministic.get("reasoning") or ""
    analysis["matched_skills"] = live_matched
    analysis["missing_skills"] = live_missing
    analysis["recommendation"] = analysis.get("recommendation") or "Review Manually"
    if isinstance(breakdown, dict):
        breakdown["matched_skills"] = live_matched
        breakdown["missing_skills"] = live_missing

    return {
        "id": a.id,
        "job_id": a.job_id,
        "resume_id": a.resume_id,
        "status": a.status,
        "created_at": a.created_at.isoformat() if isinstance(a.created_at, datetime) else a.created_at,
        "score_updated_at": a.score_updated_at.isoformat()
        if isinstance(getattr(a, "score_updated_at", None), datetime)
        else getattr(a, "score_updated_at", None),
        "ai_explanation": a.ai_explanation,
        "semantic_score": float(a.semantic_score or 0.0),
        "skills_score": float(a.skills_score or 0.0),
        "experience_score": float(a.experience_score or 0.0),
        "ai_score": float(a.ai_score or 0.0),
        "final_score": int(a.final_score or 0),
        "score_breakdown": breakdown,
        "ai_analysis": analysis,
        "job": _job_to_public(job) if job else None,
        "resume": resume_meta,
    }


@router.get("/applications/{application_id}")
def application_details(
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


@router.patch("/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    status = _normalize_application_status(payload.status)
    if status not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Invalid application status. Use not-reviewed, shortlisted, on-hold, or rejected.",
        )

    application = db.query(Application).filter(Application.id == int(application_id)).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == int(application.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="You can only update applications for your own jobs")

    application.status = normalize_application_status(status)
    db.add(application)
    db.commit()
    db.refresh(application)

    return {
        "success": True,
        "application": {
            "id": int(application.id),
            "application_id": int(application.id),
            "status": application.status,
            "job_id": int(application.job_id),
            "candidate_id": int(application.candidate_id),
            "final_score": int(application.final_score or 0),
        },
    }


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
        delete_ai_resume_analysis(db, application_id=int(a.id))
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


