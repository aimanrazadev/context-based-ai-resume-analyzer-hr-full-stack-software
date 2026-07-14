from fastapi import APIRouter

from . import job_handlers


router = APIRouter(prefix="/jobs", tags=["Jobs"])

router.add_api_route("", job_handlers.create_job, methods=["POST"], status_code=201)
router.add_api_route("", job_handlers.list_jobs, methods=["GET"])
router.add_api_route("/{job_id:int}", job_handlers.get_job, methods=["GET"])
router.add_api_route("/{job_id:int}", job_handlers.update_job, methods=["PATCH"])
router.add_api_route("/{job_id:int}", job_handlers.delete_job, methods=["DELETE"], status_code=200)
