from fastapi import APIRouter

from . import applications, jobs, rankings, resume_scans


router = APIRouter()
router.include_router(jobs.router)
router.include_router(resume_scans.router)
router.include_router(applications.router)
router.include_router(rankings.router)
