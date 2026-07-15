from datetime import datetime
import json
import logging

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.job import Job
from ..services.embedding_service import get_or_create_embedding
from ..utils.error_handlers import get_error_message, handle_database_error
from ..utils.validation import validate_integer_field, validate_job_status, validate_string_field

logger = logging.getLogger(__name__)


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


def serialize_job_json_fields(payload) -> dict[str, str | None]:
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


def create_job_embedding_background(job_id: int) -> None:
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
        logger.warning("Failed to create embedding for job %s: %s", job_id, e)
    finally:
        db.close()


def create_job_record(db: Session, *, payload, user_id: int) -> Job:
    try:
        status = validate_job_status(payload.status or "active")
    except HTTPException:
        raise

    if status != "draft":
        try:
            title = validate_string_field(payload.title, "Title", min_length=2, max_length=150, required=True)
            description = validate_string_field(payload.description, "Description", min_length=10, max_length=5000, required=True)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Validation error in create_job: %s", e)
            raise HTTPException(status_code=400, detail=get_error_message("invalid_job_data"))
    else:
        title = (payload.title or "").strip() or "Untitled Draft"
        description = payload.description or ""

    location = validate_string_field(payload.location, "Location", min_length=1, max_length=100, required=False) or ""
    salary_range = validate_string_field(payload.salary_range, "Salary range", min_length=1, max_length=50, required=False) or ""
    salary_currency = validate_string_field(payload.salary_currency, "Salary currency", min_length=1, max_length=5, required=False)
    opportunity_type = validate_string_field(payload.opportunity_type, "Opportunity type", min_length=1, max_length=20, required=False)
    job_type = validate_string_field(payload.job_type, "Job type", min_length=1, max_length=20, required=False)
    job_site = validate_string_field(payload.job_site, "Job site", min_length=1, max_length=20, required=False)
    additional_preferences = validate_string_field(payload.additional_preferences, "Additional preferences", min_length=0, max_length=2000, required=False)
    job_link = validate_string_field(payload.job_link, "Job link", min_length=1, max_length=255, required=False) or ""
    duration = validate_string_field(payload.duration, "Duration", min_length=1, max_length=100, required=False)
    short_description = validate_string_field(payload.short_description, "Short description", min_length=1, max_length=255, required=False)

    json_fields = serialize_job_json_fields(payload)
    draft_step = payload.draft_step or 1
    if draft_step < 1 or draft_step > 3:
        draft_step = 1

    job = Job(
        user_id=user_id,
        job_title=title,
        short_description=short_description or None,
        job_description=description,
        location=location or None,
        salary_range=salary_range or None,
        salary_currency=salary_currency or None,
        salary_min=validate_integer_field(payload.salary_min, "Salary min", min_value=0, max_value=10**9, required=False),
        salary_max=validate_integer_field(payload.salary_max, "Salary max", min_value=0, max_value=10**9, required=False),
        variable_min=validate_integer_field(payload.variable_min, "Variable min", min_value=0, max_value=10**9, required=False),
        variable_max=validate_integer_field(payload.variable_max, "Variable max", min_value=0, max_value=10**9, required=False),
        opportunity_type=(opportunity_type or None),
        min_experience_years=validate_integer_field(payload.min_experience_years, "Minimum experience years", min_value=0, max_value=60, required=False),
        job_type=(job_type or None),
        job_site=(job_site or None),
        openings=validate_integer_field(payload.openings, "Openings", min_value=1, max_value=100000, required=False),
        perks=json_fields.get("perks"),
        non_negotiables=json_fields.get("non_negotiables"),
        required_skills=json_fields.get("required_skills"),
        additional_preferences=additional_preferences or None,
        start_date=parse_optional_datetime(payload.start_date, "start_date"),
        duration=duration or None,
        apply_by=parse_optional_datetime(payload.apply_by, "apply_by"),
        job_link=job_link or None,
        status=status,
    )

    if status == "draft":
        if "draft_data" in json_fields:
            job.draft_data = json_fields.get("draft_data")
        job.draft_step = draft_step

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as e:
        db.rollback()
        logger.error("Database error creating job: %s", e)
        raise handle_database_error(e, "creating job")

    return job


def list_job_records(db: Session, *, mine: bool, status: str | None, user: dict) -> list[Job]:
    q = db.query(Job)

    if user.get("role") == "recruiter" and mine:
        q = q.filter(Job.user_id == int(user.get("sub")))
    if user.get("role") == "candidate":
        q = q.filter(func.lower(Job.status) == "active")

    status_norm = (status or "").strip().lower()
    if status_norm == "drafts":
        status_norm = "draft"
    if status_norm and status_norm != "all":
        q = q.filter(func.lower(Job.status) == status_norm)
    elif user.get("role") == "recruiter" and mine:
        q = q.filter(func.lower(Job.status).in_(["active", "closed"]))

    if status_norm != "deleted":
        q = q.filter(func.lower(Job.status) != "deleted")

    return q.order_by(Job.created_at.desc()).all()


def get_job_for_user(db: Session, *, job_id: int, user: dict) -> Job:
    job_id = validate_integer_field(job_id, "Job ID", min_value=1)
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    except Exception as e:
        logger.error("Database error fetching job: %s", e)
        raise handle_database_error(e, "fetching job")
    if not job:
        raise HTTPException(status_code=404, detail=get_error_message("job_not_found"))
    if user.get("role") == "candidate" and job.status != "active":
        raise HTTPException(status_code=404, detail=get_error_message("job_not_found"))
    return job


def update_job_record(db: Session, *, job_id: int, payload, user_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != user_id:
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
        status = payload.status.lower()
        if status not in {"active", "draft", "closed"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        job.status = status
        if status != "draft":
            job.draft_data = None
            job.draft_step = 1
    if payload.draft_step is not None:
        job.draft_step = int(payload.draft_step)
    if "draft_data" in json_fields:
        job.draft_data = json_fields.get("draft_data")

    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        get_or_create_embedding(db, entity_type="job", entity_id=job.id, text=job_text)
    except Exception:
        pass

    return job


def soft_delete_job(db: Session, *, job_id: int, user_id: int) -> int:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own jobs")

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

    return int(job_id)
