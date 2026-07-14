from fastapi import APIRouter

from . import job_handlers


router = APIRouter(prefix="/jobs", tags=["Jobs"])

router.add_api_route("/{job_id:int}/scan_resume_async", job_handlers.scan_resume_async, methods=["POST"])
router.add_api_route("/apply_status/{task_id}", job_handlers.apply_status, methods=["GET"])
