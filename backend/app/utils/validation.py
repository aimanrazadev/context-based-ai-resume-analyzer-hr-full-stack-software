"""
Validation utilities for input validation and error handling.
"""
import re
from typing import Any
from fastapi import HTTPException


def validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not isinstance(email, str):
        raise HTTPException(status_code=400, detail="Email is required")
    
    email = email.strip().lower()
    if len(email) > 255:
        raise HTTPException(status_code=400, detail="Email too long (max 255 characters)")
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    return email


def validate_password(password: str) -> None:
    """Validate password strength."""
    if not password or not isinstance(password, str):
        raise HTTPException(status_code=400, detail="Password is required")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="Password too long (max 128 characters)")


def validate_string_field(
    value: Any,
    field_name: str,
    min_length: int = 1,
    max_length: int = 1000,
    required: bool = True,
    pattern: str | None = None,
) -> str | None:
    """Validate a string field with common rules."""
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return None
    
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")
    
    value = value.strip()
    
    if required and not value:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
    
    if len(value) < min_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be at least {min_length} characters"
        )
    
    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must not exceed {max_length} characters"
        )
    
    if pattern and not re.match(pattern, value):
        raise HTTPException(status_code=400, detail=f"{field_name} format is invalid")
    
    return value


def validate_integer_field(
    value: Any,
    field_name: str,
    min_value: int | None = None,
    max_value: int | None = None,
    required: bool = True,
) -> int | None:
    """Validate an integer field."""
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return None
    
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"{field_name} must be a valid integer")
    
    if min_value is not None and value < min_value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be at least {min_value}"
        )
    
    if max_value is not None and value > max_value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must not exceed {max_value}"
        )
    
    return value


def validate_role(role: str) -> str:
    """Validate user role."""
    if not role or not isinstance(role, str):
        raise HTTPException(status_code=400, detail="Role is required")
    
    role = role.strip().lower()
    valid_roles = {"admin", "recruiter", "candidate"}
    
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    return role


def validate_job_status(status: str | None) -> str:
    """Validate job status."""
    if not status:
        return "active"
    
    status = status.strip().lower()
    valid_statuses = {"active", "draft", "closed", "deleted"}
    
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    return status


def validate_interview_outcome(outcome: str | None) -> str | None:
    """Validate interview outcome."""
    if not outcome:
        return None
    
    outcome = outcome.strip().lower()
    valid_outcomes = {
        "scheduled", "completed", "cancelled",
        "passed", "failed", "on_hold", "no_show"
    }
    
    if outcome not in valid_outcomes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome. Must be one of: {', '.join(valid_outcomes)}"
        )
    
    return outcome


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and other attacks."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Remove any path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove any null bytes
    filename = filename.replace("\x00", "")
    
    # Remove directory traversal sequences
    filename = filename.replace("..", "_")
    
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip(".")
    
    # Ensure it's not too long
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="Filename too long")
    
    # Ensure it has some content
    if not filename or filename == "_":
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    return filename
