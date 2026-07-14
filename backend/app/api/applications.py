from fastapi import APIRouter

from . import job_handlers


router = APIRouter(prefix="/jobs", tags=["Jobs"])

router.add_api_route("/{job_id:int}/apply_from_scan", job_handlers.apply_from_scan, methods=["POST"])
router.add_api_route("/applied", job_handlers.list_applied_jobs, methods=["GET"])
router.add_api_route("/{job_id:int}/my_application", job_handlers.my_application_for_job, methods=["GET"])
router.add_api_route("/applications/{application_id}", job_handlers.application_details, methods=["GET"])
router.add_api_route("/applications/{application_id}/resume", job_handlers.download_application_resume, methods=["GET"])
router.add_api_route("/applications/{application_id}/status", job_handlers.update_application_status, methods=["PATCH"])
router.add_api_route("/applications/{application_id}", job_handlers.delete_application, methods=["DELETE"])
