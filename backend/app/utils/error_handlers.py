"""
Centralized error handling and user-friendly error messages.
"""
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)


ERROR_MESSAGES = {
    "job_not_found": "Job posting not found or has been removed.",
    "invalid_job_data": "Job information is incomplete. Please fill in all required fields.",
    "server_error": "Something went wrong on our end. Please try again later.",
    "database_error": "Database connection issue. Please try again later.",
    "validation_error": "Please check your input and try again.",
}


def get_error_message(error_key: str, default: str | None = None) -> str:
    """Get a user-friendly error message."""
    return ERROR_MESSAGES.get(error_key, default or ERROR_MESSAGES["server_error"])


def handle_database_error(error: Exception, operation: str = "") -> HTTPException:
    """Handle database errors with user-friendly messages."""
    logger.error(f"Database error during {operation}: {error}")
    
    error_str = str(error).lower()
    
    # Detect specific DB errors
    if "duplicate" in error_str or "unique" in error_str:
        return HTTPException(
            status_code=409,
            detail="This record already exists. Please check your input."
        )
    
    if "foreign key" in error_str:
        return HTTPException(
            status_code=400,
            detail="Invalid reference. The related record may have been deleted."
        )
    
    if "connection" in error_str or "operational" in error_str:
        return HTTPException(
            status_code=503,
            detail=get_error_message("database_error")
        )
    
    return HTTPException(
        status_code=500,
        detail=get_error_message("server_error")
    )
