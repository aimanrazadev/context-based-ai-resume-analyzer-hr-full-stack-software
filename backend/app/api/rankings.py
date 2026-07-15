from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.application import Application
from ..models.job import Job
from ..services.application_serializer import job_to_public
from ..utils.roles import recruiter_only
from .recruiter import _application_row


router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id:int}/ranked_candidates")
def ranked_candidates(
    job_id: int,
    db: Session = Depends(get_db),
    user=Depends(recruiter_only),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if int(job.user_id or 0) != int(user.get("sub")):
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

    return {
        "success": True,
        "job": job_to_public(job),
        "candidates": [_application_row(db, app, job=job, include_job=False) for app in apps],
    }
