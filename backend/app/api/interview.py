import json
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from ..database import get_db
from ..models.application import Application
from ..models.candidate import Candidate
from ..models.interview import Interview
from ..models.job import Job
from ..models.user import User
from ..utils.dependencies import get_current_user
from ..utils.roles import candidate_only, recruiter_only
from ..services.emailer import send_interview_scheduled_email
from ..utils.validation import validate_integer_field, validate_string_field
from ..utils.error_handlers import get_error_message, handle_database_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["Interviews"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_or_create_candidate(db: Session, *, user_id: int) -> Candidate:
    user = db.query(User).filter(User.id == int(user_id)).first()
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


def _get_interview_transcript(interview: Interview) -> list[dict]:
    raw = getattr(interview, "transcript", None) or ""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _set_interview_transcript(interview: Interview, transcript: list[dict]) -> None:
    interview.transcript = json.dumps(transcript or [], ensure_ascii=False)


def _ensure_candidate_owns_application(db: Session, *, application_id: int, user_id: int) -> Application:
    candidate = _find_or_create_candidate(db, user_id=int(user_id))
    a = (
        db.query(Application)
        .filter(Application.id == int(application_id), Application.candidate_id == int(candidate.id))
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    return a


def _ensure_shared_access(db: Session, *, interview: Interview, user: dict) -> None:
    role = user.get("role")
    if role == "candidate":
        candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
        a = interview.application
        if not a or int(a.candidate_id or 0) != int(candidate.id):
            raise HTTPException(status_code=403, detail="Forbidden")
        return
    if role == "recruiter":
        a = interview.application
        job = a.job if a else None
        if not job or int(job.user_id or 0) != int(user.get("sub")):
            raise HTTPException(status_code=403, detail="Forbidden")
        return
    raise HTTPException(status_code=403, detail="Forbidden")


def _safe_application_status(db: Session, desired: str) -> str | None:
    """
    Keep consistent with job.py: handle MySQL ENUM limitations; default to desired for non-MySQL.
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
        ct_low = str(column_type).lower()
        if ct_low.startswith("enum("):
            inner = column_type[len("enum(") : -1]
            raw_vals = [v.strip() for v in inner.split(",") if v.strip()]
            vals: list[str] = []
            for v in raw_vals:
                v = v.strip()
                if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                    v = v[1:-1]
                vals.append(v)
            if desired in vals:
                return desired
            for cand in ("scheduled", "interview_scheduled", "submitted", "applied", "pending"):
                if cand in vals:
                    return cand
            return vals[0] if vals else None
        return desired
    except Exception:
        return desired


def _parse_scheduled_at(*, scheduled_at: str, tz: str | None) -> datetime:
    raw = (scheduled_at or "").strip()
    if not raw:
        raise ValueError("scheduled_at is required")
    # Allow ISO with timezone, or naive ISO + timezone string.
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        if tz and ZoneInfo is not None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(tz))
            except Exception:
                # On Windows, IANA tz database may be missing; fall back safely.
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class InterviewScheduleIn(BaseModel):
    application_id: int = Field(..., ge=1)
    scheduled_at: str = Field(..., min_length=6)
    timezone: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    mode: str | None = None
    meeting_link: str | None = None
    location: str | None = None
    interviewer_name: str | None = None
    recruiter_notes: str | None = None


@router.post("/schedule")
def schedule_interview(
    body: InterviewScheduleIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    """
    Recruiter-driven interview invite:
      - Recruiter selects an application
      - Creates (or reuses) an Interview row with status='scheduled'
      - Candidate sees it in their Interviews tab (acts as a notification)
    """
    # Validate application_id
    try:
        application_id = validate_integer_field(
            body.application_id, "Application ID",
            min_value=1, required=True
        )
    except HTTPException:
        raise
    
    # Fetch application with error handling
    try:
        a = db.query(Application).filter(Application.id == application_id).first()
    except Exception as e:
        logger.error(f"Database error fetching application: {e}")
        raise handle_database_error(e, "fetching application")
    
    if not a:
        raise HTTPException(
            status_code=404,
            detail=get_error_message("application_not_found")
        )

    job = a.job
    if not job:
        raise HTTPException(
            status_code=404,
            detail=get_error_message("job_not_found")
        )
    
    # Verify recruiter owns this job
    if int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(
            status_code=403,
            detail=get_error_message("forbidden")
        )

    # Validate scheduled_at
    try:
        scheduled_dt = _parse_scheduled_at(scheduled_at=body.scheduled_at, tz=body.timezone)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=get_error_message("invalid_schedule")
        )
    except Exception as e:
        logger.error(f"Error parsing scheduled_at: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid schedule date format"
        )

    # Validate optional fields
    mode = validate_string_field(
        body.mode, "Interview mode",
        min_length=1, max_length=50, required=False
    )
    meeting_link = validate_string_field(
        body.meeting_link, "Meeting link",
        min_length=1, max_length=500, required=False
    )
    location = validate_string_field(
        body.location, "Location",
        min_length=1, max_length=200, required=False
    )
    interviewer_name = validate_string_field(
        body.interviewer_name, "Interviewer name",
        min_length=1, max_length=100, required=False
    )
    recruiter_notes = validate_string_field(
        body.recruiter_notes, "Recruiter notes",
        min_length=1, max_length=2000, required=False
    )

    # Validate duration
    duration_minutes = None
    if body.duration_minutes is not None:
        try:
            duration_minutes = validate_integer_field(
                body.duration_minutes, "Duration",
                min_value=5, max_value=480, required=False
            )
        except HTTPException:
            raise

    # Avoid duplicates: reuse the latest interview for the application if present.
    try:
        existing = (
            db.query(Interview)
            .filter(Interview.application_id == int(a.id))
            .order_by(Interview.created_at.desc())
            .first()
        )
    except Exception as e:
        logger.error(f"Database error checking existing interview: {e}")
        raise handle_database_error(e, "checking existing interview")
    
    if existing and str(getattr(existing, "status", "") or "").lower() in {"scheduled", "completed", "evaluated"}:
        it = existing
    else:
        it = Interview(application_id=int(a.id))
        try:
            db.add(it)
            db.commit()
            db.refresh(it)
        except Exception as e:
            db.rollback()
            logger.error(f"Database error creating interview: {e}")
            raise handle_database_error(e, "creating interview")

    # Persist schedule fields
    it.scheduled_at = scheduled_dt
    it.timezone = (body.timezone or "").strip() or None
    it.duration_minutes = duration_minutes
    it.mode = mode or None
    it.meeting_link = meeting_link or None
    it.location = location or None
    it.interviewer_name = interviewer_name or None
    it.recruiter_notes = recruiter_notes or None
    it.status = "scheduled"
    it.updated_at = datetime.now(timezone.utc)
    
    # Update application status (best-effort for MySQL ENUM)
    try:
        a.status = _safe_application_status(db, "interview_scheduled")
        db.add(a)
        db.add(it)
        db.commit()
        db.refresh(it)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating interview: {e}")
        raise handle_database_error(e, "updating interview")

    # Notify candidate by email (non-blocking, best-effort)
    def _safe_email(**kwargs):  # noqa: ANN001
        try:
            import sys
            print(f"[INTERVIEW] Attempting to send email to {kwargs.get('to_email')}...", file=sys.stderr)
            send_interview_scheduled_email(**kwargs)
            print(f"[INTERVIEW] Email sent successfully!", file=sys.stderr)
        except Exception as e:
            # Never fail scheduling due to email issues.
            import sys
            print(f"[INTERVIEW] Email failed (non-blocking): {type(e).__name__}: {str(e)}", file=sys.stderr)
            return

    try:
        cand = a.candidate
        to_email = (cand.email if cand else "") or ""
        if to_email:
            scheduled_text = body.scheduled_at
            try:
                scheduled_text = it.scheduled_at.astimezone(timezone.utc).isoformat() if it.scheduled_at else body.scheduled_at
            except Exception:
                scheduled_text = body.scheduled_at
            background_tasks.add_task(
                _safe_email,
                to_email=to_email,
                candidate_name=(cand.name if cand else None),
                recruiter_name=(user.get("name") or None),
                job_title=(job.job_title if job else None),
                scheduled_at_text=scheduled_text,
                timezone=(it.timezone or body.timezone),
                mode=(it.mode or body.mode),
                meeting_link=it.meeting_link,
                location=it.location,
            )
    except Exception as e:
        logger.warning(f"Failed to queue email notification: {e}")
        # Don't fail the scheduling if email fails

    return {"success": True, "interview": {"id": int(it.id), "application_id": int(it.application_id), "status": it.status}}


class InterviewUpdateIn(BaseModel):
    scheduled_at: str | None = None
    timezone: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    mode: str | None = None
    meeting_link: str | None = None
    location: str | None = None
    interviewer_name: str | None = None
    recruiter_notes: str | None = None


@router.patch("/{interview_id}")
def update_interview(
    interview_id: int,
    body: InterviewUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    it = db.query(Interview).filter(Interview.id == int(interview_id)).first()
    if not it:
        raise HTTPException(status_code=404, detail="Interview not found")
    a = it.application
    job = a.job if a else None
    if not job or int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.scheduled_at:
        it.scheduled_at = _parse_scheduled_at(scheduled_at=body.scheduled_at, tz=body.timezone or it.timezone)
    if body.timezone is not None:
        it.timezone = body.timezone.strip() or None
    if body.duration_minutes is not None:
        it.duration_minutes = int(body.duration_minutes)
    if body.mode is not None:
        it.mode = body.mode.strip() or None
    if body.meeting_link is not None:
        it.meeting_link = body.meeting_link.strip() or None
    if body.location is not None:
        it.location = body.location.strip() or None
    if body.interviewer_name is not None:
        it.interviewer_name = body.interviewer_name.strip() or None
    if body.recruiter_notes is not None:
        it.recruiter_notes = body.recruiter_notes.strip() or None

    it.updated_at = datetime.now(timezone.utc)
    db.add(it)
    db.commit()
    db.refresh(it)
    return {"success": True, "interview": {"id": int(it.id), "status": it.status}}


class InterviewCompleteIn(BaseModel):
    feedback: str | None = None


@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: int,
    body: InterviewCompleteIn,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    it = db.query(Interview).filter(Interview.id == int(interview_id)).first()
    if not it:
        raise HTTPException(status_code=404, detail="Interview not found")
    a = it.application
    job = a.job if a else None
    if not job or int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Forbidden")

    it.status = "completed"
    it.completed_at = datetime.now(timezone.utc)
    if body.feedback is not None:
        it.feedback = body.feedback.strip() or None
    it.updated_at = datetime.now(timezone.utc)
    db.add(it)

    try:
        if a:
            a.status = _safe_application_status(db, "interview_completed")
            db.add(a)
    except Exception:
        pass

    db.commit()
    db.refresh(it)
    return {"success": True, "interview": {"id": int(it.id), "status": it.status}}


class InterviewEvaluateIn(BaseModel):
    outcome: str = Field(..., min_length=2)  # pass | fail | on_hold
    remarks: str | None = None


@router.post("/{interview_id}/evaluate")
def evaluate_interview(
    interview_id: int,
    body: InterviewEvaluateIn,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    it = db.query(Interview).filter(Interview.id == int(interview_id)).first()
    if not it:
        raise HTTPException(status_code=404, detail="Interview not found")
    a = it.application
    job = a.job if a else None
    if not job or int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Forbidden")

    out = str(body.outcome or "").strip().lower()
    if out not in {"pass", "fail", "on_hold"}:
        raise HTTPException(status_code=400, detail="Invalid outcome (pass|fail|on_hold)")

    it.status = "evaluated"
    it.outcome = out
    it.evaluated_at = datetime.now(timezone.utc)
    if body.remarks is not None:
        # store in feedback if present; keeps schema minimal
        it.feedback = (it.feedback or "").strip()
        extra = body.remarks.strip()
        it.feedback = (it.feedback + ("\n\n" if it.feedback and extra else "") + extra) if extra else (it.feedback or None)
    it.updated_at = datetime.now(timezone.utc)
    db.add(it)

    try:
        if a:
            new_status = {"pass": "interview_pass", "fail": "interview_fail", "on_hold": "interview_on_hold"}[out]
            a.status = _safe_application_status(db, new_status)
            db.add(a)
    except Exception:
        pass

    db.commit()
    db.refresh(it)
    return {"success": True, "interview": {"id": int(it.id), "status": it.status, "outcome": it.outcome}}


@router.get("/mine")
def my_interviews(
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    rows = (
        db.query(Interview)
        .join(Application, Interview.application_id == Application.id)
        .filter(Application.candidate_id == int(candidate.id))
        .order_by(Interview.created_at.desc())
        .all()
    )
    items: list[dict] = []
    for it in rows:
        a = it.application
        job = a.job if a else None
        items.append(
            {
                "id": int(it.id),
                "application_id": int(it.application_id),
                "status": getattr(it, "status", None),
                "overall_fit": float(it.overall_fit or 0.0) if it.overall_fit is not None else None,
                "created_at": it.created_at.isoformat() if isinstance(it.created_at, datetime) else it.created_at,
                "job": {"id": job.id, "title": job.job_title} if job else None,
                "scheduled_at": it.scheduled_at.isoformat() if isinstance(getattr(it, "scheduled_at", None), datetime) else None,
                "timezone": getattr(it, "timezone", None),
                "mode": getattr(it, "mode", None),
                "meeting_link": getattr(it, "meeting_link", None),
                "location": getattr(it, "location", None),
            }
        )
    return {"success": True, "interviews": items}


@router.get("/{interview_id}")
def interview_details(
    interview_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    interview = db.query(Interview).filter(Interview.id == int(interview_id)).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    _ensure_shared_access(db, interview=interview, user=user)

    transcript = _get_interview_transcript(interview)
    a = interview.application
    job = a.job if a else None
    candidate = a.candidate if a else None

    return {
        "success": True,
        "interview": {
            "id": int(interview.id),
            "application_id": int(interview.application_id),
            "status": getattr(interview, "status", None),
            "clarity_score": float(interview.clarity_score or 0.0) if interview.clarity_score is not None else None,
            "relevance_score": float(interview.relevance_score or 0.0) if interview.relevance_score is not None else None,
            "overall_fit": float(interview.overall_fit or 0.0) if interview.overall_fit is not None else None,
            "summary_json": None,
            "transcript": transcript,
            "job": {"id": job.id, "title": job.job_title} if job else None,
            "candidate": {"id": candidate.id, "name": candidate.name, "email": candidate.email} if candidate else None,
            "scheduled_at": interview.scheduled_at.isoformat() if isinstance(getattr(interview, "scheduled_at", None), datetime) else None,
            "timezone": getattr(interview, "timezone", None),
            "duration_minutes": getattr(interview, "duration_minutes", None),
            "mode": getattr(interview, "mode", None),
            "meeting_link": getattr(interview, "meeting_link", None),
            "location": getattr(interview, "location", None),
            "interviewer_name": getattr(interview, "interviewer_name", None),
            "recruiter_notes": getattr(interview, "recruiter_notes", None),
            "feedback": getattr(interview, "feedback", None),
            "outcome": getattr(interview, "outcome", None),
            "completed_at": interview.completed_at.isoformat() if isinstance(getattr(interview, "completed_at", None), datetime) else None,
            "evaluated_at": interview.evaluated_at.isoformat() if isinstance(getattr(interview, "evaluated_at", None), datetime) else None,
            "created_at": interview.created_at.isoformat()
            if isinstance(interview.created_at, datetime)
            else interview.created_at,
        },
    }


@router.get("/job/{job_id}")
def job_interviews(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = db.query(Job).filter(Job.id == int(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if int(job.user_id or 0) != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = (
        db.query(Interview)
        .join(Application, Interview.application_id == Application.id)
        .filter(Application.job_id == int(job_id))
        .order_by(func.coalesce(Interview.overall_fit, -1).desc(), Interview.created_at.desc())
        .all()
    )
    items: list[dict] = []
    for it in rows:
        a = it.application
        cand = a.candidate if a else None
        items.append(
            {
                "id": int(it.id),
                "application_id": int(it.application_id),
                "candidate": {"id": cand.id, "name": cand.name, "email": cand.email} if cand else None,
                "status": getattr(it, "status", None),
                "clarity_score": float(it.clarity_score or 0.0) if it.clarity_score is not None else None,
                "relevance_score": float(it.relevance_score or 0.0) if it.relevance_score is not None else None,
                "overall_fit": float(it.overall_fit or 0.0) if it.overall_fit is not None else None,
                "created_at": it.created_at.isoformat() if isinstance(it.created_at, datetime) else it.created_at,
            }
        )
    return {"success": True, "job": {"id": job.id, "title": job.job_title}, "interviews": items}

