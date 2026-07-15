from fastapi import APIRouter

from . import applications, job_crud, rankings, resume_scans


router = APIRouter()
router.include_router(job_crud.router)
router.include_router(resume_scans.router)
router.include_router(applications.router)
router.include_router(rankings.router)
