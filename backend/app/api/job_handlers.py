from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..models.application import Application
from ..models.job import Job
from ..models.resume import Resume
from ..services.application_service import (
    create_application_from_completed_scan,
    delete_application_for_user,
    find_candidate_job_application,
    find_or_create_candidate,
    list_candidate_applications,
    update_application_status_for_recruiter,
)
from ..services.application_serializer import (
    already_applied_response,
    application_details_payload,
    application_status_payload,
    applied_jobs_payload,
    created_application_response,
    job_to_public,
)
from ..services.job_service import (
    create_job_embedding_background,
    create_job_record,
    get_job_for_user,
    list_job_records,
    soft_delete_job,
    update_job_record,
)
from ..services.resume_scan_service import run_scan_task
from ..modules.resumes.storage import (
    build_resume_storage_path,
    save_upload_file,
    validate_resume_upload,
)
from ..services.progress_tracker import create_task, get_task, public_view, update_task
from ..utils.dependencies import get_current_user
from ..utils.roles import candidate_only, recruiter_only

router = APIRouter(prefix="/jobs", tags=["Jobs"])

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/octet-stream",
}
MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5MB


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


@router.post("", status_code=201)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = create_job_record(db, payload=payload, user_id=int(user.get("sub")))
    background_tasks.add_task(create_job_embedding_background, int(job.id))
    return {"success": True, "job": job_to_public(job)}


@router.get("")
def list_jobs(
    mine: bool = Query(default=False, description="If true and role is recruiter, return only your jobs"),
    status: str | None = Query(default=None, description="active/closed/draft/deleted"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    items = [job_to_public(job) for job in list_job_records(db, mine=mine, status=status, user=user)]
    return {"success": True, "jobs": items}


@router.get("/{job_id:int}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    job = get_job_for_user(db, job_id=job_id, user=user)
    include_draft = user.get("role") == "recruiter" and job.status == "draft"
    return {"success": True, "job": job_to_public(job, include_draft=include_draft)}


@router.patch("/{job_id:int}")
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = update_job_record(db, job_id=job_id, payload=payload, user_id=int(user.get("sub")))
    return {"success": True, "job": job_to_public(job)}


@router.delete("/{job_id:int}", status_code=200)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    return {"success": True, "deleted_job_id": soft_delete_job(db, job_id=job_id, user_id=int(user.get("sub")))}
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

    candidate = find_or_create_candidate(db, user_id=int(user.get("sub")))
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
        run_scan_task,
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
    result = create_application_from_completed_scan(
        db,
        job_id=int(job_id),
        user_id=int(user.get("sub")),
        task_id=payload.task_id,
        upload_dir=UPLOAD_DIR,
    )
    if result.get("already_applied"):
        return already_applied_response(result["application"])

    return created_application_response(
        application=result["application"],
        job=result["job"],
        ai_analysis=result.get("ai_analysis") or {},
        breakdown=result.get("breakdown") or {},
    )


@router.get("/applied")
def list_applied_jobs(
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = find_or_create_candidate(db, user_id=int(user.get("sub")))
    apps = list_candidate_applications(db, candidate_id=int(candidate.id))
    return {"success": True, "applications": applied_jobs_payload(apps)}


@router.get("/{job_id:int}/my_application")
def my_application_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = find_or_create_candidate(db, user_id=int(user.get("sub")))
    application = find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if not application:
        return {"success": True, "already_applied": False, "application": None}
    return already_applied_response(application)

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
        candidate = find_or_create_candidate(db, user_id=int(user.get("sub")))
        if int(a.candidate_id or 0) != int(candidate.id):
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"success": True, "application": application_details_payload(db=db, application=a, candidate=candidate)}

    if role == "recruiter":
        job = a.job
        if not job or int(job.user_id or 0) != int(user.get("sub")):
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"success": True, "application": application_details_payload(db=db, application=a, candidate=None)}

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
        candidate = find_or_create_candidate(db, user_id=int(user.get("sub")))
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
    application = update_application_status_for_recruiter(
        db,
        application_id=application_id,
        status=payload.status,
        recruiter_id=int(user.get("sub")),
    )
    return {
        "success": True,
        "application": application_status_payload(application),
    }


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    job_id = delete_application_for_user(db, application_id=application_id, user=user, upload_dir=UPLOAD_DIR)
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


