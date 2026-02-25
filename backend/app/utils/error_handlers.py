"""
Centralized error handling and user-friendly error messages.
"""
import logging
from typing import Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, status_code: int = 500, details: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    """Validation error."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=400, details=details)


class NotFoundError(AppError):
    """Resource not found error."""
    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(message, status_code=404, details=details)


class UnauthorizedError(AppError):
    """Unauthorized access error."""
    def __init__(self, message: str = "Unauthorized access", details: dict | None = None):
        super().__init__(message, status_code=401, details=details)


class ForbiddenError(AppError):
    """Forbidden access error."""
    def __init__(self, message: str = "Access forbidden", details: dict | None = None):
        super().__init__(message, status_code=403, details=details)


class AIServiceError(AppError):
    """AI service error."""
    def __init__(self, message: str = "AI service temporarily unavailable", details: dict | None = None):
        super().__init__(message, status_code=503, details=details)


class FileUploadError(AppError):
    """File upload error."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=400, details=details)


class DatabaseError(AppError):
    """Database error."""
    def __init__(self, message: str = "Database operation failed", details: dict | None = None):
        super().__init__(message, status_code=500, details=details)


# User-friendly error messages
ERROR_MESSAGES = {
    # Authentication
    "invalid_credentials": "Invalid email or password. Please try again.",
    "email_exists": "An account with this email already exists. Please login instead.",
    "weak_password": "Password must be at least 6 characters long.",
    "session_expired": "Your session has expired. Please login again.",
    
    # File uploads
    "file_too_large": "File is too large. Maximum size is 5MB.",
    "invalid_file_type": "Invalid file type. Please upload a PDF or DOCX file.",
    "file_corrupted": "File appears to be corrupted. Please try uploading again.",
    "file_processing_failed": "Failed to process your file. Please ensure it's a valid resume document.",
    
    # AI services
    "ai_unavailable": "AI analysis is temporarily unavailable. Please try again in a few moments.",
    "ai_timeout": "AI analysis is taking longer than expected. Your request has been queued.",
    "ai_failed": "AI analysis encountered an error. Using basic analysis instead.",
    
    # Jobs
    "job_not_found": "Job posting not found or has been removed.",
    "job_closed": "This job posting is no longer accepting applications.",
    "already_applied": "You have already applied to this job.",
    "invalid_job_data": "Job information is incomplete. Please fill in all required fields.",
    
    # Applications
    "application_not_found": "Application not found. It may have been withdrawn.",
    "no_resume": "Please upload a resume before applying to jobs.",
    "application_failed": "Failed to submit application. Please try again.",
    
    # Interviews
    "interview_not_found": "Interview not found or has been cancelled.",
    "invalid_schedule": "Invalid interview schedule. Please check the date and time.",
    "schedule_conflict": "This time slot conflicts with another interview.",
    
    # General
    "unauthorized": "Please login to access this feature.",
    "forbidden": "You don't have permission to access this resource.",
    "not_found": "The requested resource was not found.",
    "server_error": "Something went wrong on our end. Please try again later.",
    "database_error": "Database connection issue. Please try again later.",
    "validation_error": "Please check your input and try again.",
}


def get_error_message(error_key: str, default: str | None = None) -> str:
    """Get a user-friendly error message."""
    return ERROR_MESSAGES.get(error_key, default or ERROR_MESSAGES["server_error"])


def handle_file_upload_error(error: Exception, filename: str = "") -> HTTPException:
    """Handle file upload errors with user-friendly messages."""
    logger.error(f"File upload error for {filename}: {error}")
    
    if isinstance(error, HTTPException):
        return error
    
    error_str = str(error).lower()
    
    if "size" in error_str or "too large" in error_str:
        return HTTPException(
            status_code=413,
            detail=get_error_message("file_too_large")
        )
    
    if "type" in error_str or "format" in error_str:
        return HTTPException(
            status_code=400,
            detail=get_error_message("invalid_file_type")
        )
    
    if "corrupt" in error_str or "invalid" in error_str:
        return HTTPException(
            status_code=400,
            detail=get_error_message("file_corrupted")
        )
    
    return HTTPException(
        status_code=500,
        detail=get_error_message("file_processing_failed")
    )


def handle_ai_service_error(error: Exception, operation: str = "analysis") -> dict:
    """
    Handle AI service errors gracefully with fallback.
    Returns a dict with status and user-friendly message.
    """
    logger.error(f"AI service error during {operation}: {error}")
    
    error_str = str(error).lower()
    
    if "timeout" in error_str:
        return {
            "success": False,
            "fallback": True,
            "message": get_error_message("ai_timeout"),
            "error_type": "timeout"
        }
    
    if "unavailable" in error_str or "503" in error_str:
        return {
            "success": False,
            "fallback": True,
            "message": get_error_message("ai_unavailable"),
            "error_type": "unavailable"
        }
    
    return {
        "success": False,
        "fallback": True,
        "message": get_error_message("ai_failed"),
        "error_type": "error"
    }


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


def create_error_response(
    status_code: int,
    message: str,
    details: dict | None = None
) -> JSONResponse:
    """Create a standardized error response."""
    content = {
        "success": False,
        "error": message,
    }
    
    if details:
        content["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


def safe_execute(func, *args, fallback_value: Any = None, log_error: bool = True, **kwargs):
    """
    Safely execute a function with error handling.
    Returns fallback_value if an error occurs.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"Error in {func.__name__}: {e}")
        return fallback_value
