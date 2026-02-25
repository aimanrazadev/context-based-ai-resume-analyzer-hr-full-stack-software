"""
Module 13 - Validation and Error Handling Tests
Tests input validation, error handlers, and edge cases
"""
import pytest
from fastapi import HTTPException

from backend.app.utils.validation import (
    validate_email,
    validate_password,
    validate_string_field,
    validate_integer_field,
    validate_role,
    validate_job_status,
    validate_interview_outcome,
    sanitize_filename,
)
from backend.app.utils.error_handlers import (
    get_error_message,
    handle_file_upload_error,
    handle_ai_service_error,
    handle_database_error,
)


class TestEmailValidation:
    def test_valid_email(self):
        assert validate_email("test@example.com") == "test@example.com"
        assert validate_email("USER@EXAMPLE.COM") == "user@example.com"
        assert validate_email("  test@example.com  ") == "test@example.com"
    
    def test_invalid_email_format(self):
        with pytest.raises(HTTPException) as exc:
            validate_email("invalid")
        assert exc.value.status_code == 400
        assert "Invalid email format" in str(exc.value.detail)
    
    def test_email_missing_at(self):
        with pytest.raises(HTTPException) as exc:
            validate_email("testexample.com")
        assert exc.value.status_code == 400
    
    def test_email_too_long(self):
        long_email = "a" * 250 + "@test.com"
        with pytest.raises(HTTPException) as exc:
            validate_email(long_email)
        assert exc.value.status_code == 400
        assert "too long" in str(exc.value.detail).lower()
    
    def test_empty_email(self):
        with pytest.raises(HTTPException) as exc:
            validate_email("")
        assert exc.value.status_code == 400


class TestPasswordValidation:
    def test_valid_password(self):
        validate_password("password123")
        validate_password("123456")  # Minimum 6 chars
    
    def test_password_too_short(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("12345")
        assert exc.value.status_code == 400
        assert "at least 6 characters" in str(exc.value.detail)
    
    def test_password_too_long(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("a" * 129)
        assert exc.value.status_code == 400
        assert "too long" in str(exc.value.detail).lower()
    
    def test_empty_password(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("")
        assert exc.value.status_code == 400


class TestStringFieldValidation:
    def test_valid_string(self):
        result = validate_string_field("Test Title", "Title", min_length=2, max_length=50)
        assert result == "Test Title"
    
    def test_string_too_short(self):
        with pytest.raises(HTTPException) as exc:
            validate_string_field("A", "Title", min_length=2)
        assert exc.value.status_code == 400
        assert "at least 2 characters" in str(exc.value.detail)
    
    def test_string_too_long(self):
        with pytest.raises(HTTPException) as exc:
            validate_string_field("A" * 51, "Title", max_length=50)
        assert exc.value.status_code == 400
        assert "not exceed 50 characters" in str(exc.value.detail)
    
    def test_optional_field_none(self):
        result = validate_string_field(None, "Optional", required=False)
        assert result is None
    
    def test_required_field_none(self):
        with pytest.raises(HTTPException) as exc:
            validate_string_field(None, "Required", required=True)
        assert exc.value.status_code == 400
        assert "is required" in str(exc.value.detail)
    
    def test_whitespace_trimming(self):
        result = validate_string_field("  test  ", "Field")
        assert result == "test"


class TestIntegerFieldValidation:
    def test_valid_integer(self):
        result = validate_integer_field(42, "Count", min_value=1, max_value=100)
        assert result == 42
    
    def test_integer_too_small(self):
        with pytest.raises(HTTPException) as exc:
            validate_integer_field(0, "Count", min_value=1)
        assert exc.value.status_code == 400
        assert "at least 1" in str(exc.value.detail)
    
    def test_integer_too_large(self):
        with pytest.raises(HTTPException) as exc:
            validate_integer_field(101, "Count", max_value=100)
        assert exc.value.status_code == 400
        assert "not exceed 100" in str(exc.value.detail)
    
    def test_string_to_integer_conversion(self):
        result = validate_integer_field("42", "Count")
        assert result == 42
    
    def test_invalid_string_to_integer(self):
        with pytest.raises(HTTPException) as exc:
            validate_integer_field("abc", "Count")
        assert exc.value.status_code == 400
        assert "valid integer" in str(exc.value.detail)


class TestRoleValidation:
    def test_valid_roles(self):
        assert validate_role("recruiter") == "recruiter"
        assert validate_role("candidate") == "candidate"
        assert validate_role("admin") == "admin"
        assert validate_role("RECRUITER") == "recruiter"
    
    def test_invalid_role(self):
        with pytest.raises(HTTPException) as exc:
            validate_role("invalid_role")
        assert exc.value.status_code == 400
        assert "Invalid role" in str(exc.value.detail)


class TestJobStatusValidation:
    def test_valid_statuses(self):
        assert validate_job_status("active") == "active"
        assert validate_job_status("draft") == "draft"
        assert validate_job_status("closed") == "closed"
        assert validate_job_status("ACTIVE") == "active"
    
    def test_default_status(self):
        assert validate_job_status(None) == "active"
        assert validate_job_status("") == "active"
    
    def test_invalid_status(self):
        with pytest.raises(HTTPException) as exc:
            validate_job_status("invalid")
        assert exc.value.status_code == 400


class TestInterviewOutcomeValidation:
    def test_valid_outcomes(self):
        assert validate_interview_outcome("scheduled") == "scheduled"
        assert validate_interview_outcome("completed") == "completed"
        assert validate_interview_outcome("cancelled") == "cancelled"
        assert validate_interview_outcome("PASSED") == "passed"
    
    def test_none_outcome(self):
        assert validate_interview_outcome(None) is None
        assert validate_interview_outcome("") is None
    
    def test_invalid_outcome(self):
        with pytest.raises(HTTPException) as exc:
            validate_interview_outcome("invalid")
        assert exc.value.status_code == 400


class TestFilenameSanitization:
    def test_valid_filename(self):
        assert sanitize_filename("resume.pdf") == "resume.pdf"
        assert sanitize_filename("my_resume.docx") == "my_resume.docx"
    
    def test_directory_traversal(self):
        result = sanitize_filename("../../etc/passwd.pdf")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result
    
    def test_remove_path_separators(self):
        result = sanitize_filename("path/to/file.pdf")
        assert "/" not in result
        assert result == "path_to_file.pdf"
    
    def test_remove_null_bytes(self):
        result = sanitize_filename("file\x00.pdf")
        assert "\x00" not in result
    
    def test_remove_leading_dots(self):
        result = sanitize_filename(".hidden_file.pdf")
        assert result == "hidden_file.pdf"
    
    def test_empty_filename(self):
        with pytest.raises(HTTPException) as exc:
            sanitize_filename("")
        assert exc.value.status_code == 400
    
    def test_filename_too_long(self):
        with pytest.raises(HTTPException) as exc:
            sanitize_filename("a" * 256 + ".pdf")
        assert exc.value.status_code == 400


class TestErrorMessages:
    def test_get_predefined_message(self):
        msg = get_error_message("invalid_credentials")
        assert "Invalid email or password" in msg
    
    def test_get_file_error_message(self):
        msg = get_error_message("file_too_large")
        assert "5MB" in msg
    
    def test_get_ai_error_message(self):
        msg = get_error_message("ai_unavailable")
        assert "AI analysis" in msg
    
    def test_get_default_message(self):
        msg = get_error_message("nonexistent_key")
        assert "went wrong" in msg.lower()


class TestFileUploadErrorHandler:
    def test_handle_size_error(self):
        error = Exception("File size too large")
        result = handle_file_upload_error(error, "test.pdf")
        assert isinstance(result, HTTPException)
        assert result.status_code == 413
    
    def test_handle_type_error(self):
        error = Exception("Invalid file type")
        result = handle_file_upload_error(error, "test.exe")
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
    
    def test_handle_generic_error(self):
        error = Exception("Unknown error")
        result = handle_file_upload_error(error, "test.pdf")
        assert isinstance(result, HTTPException)
        assert result.status_code == 500


class TestAIServiceErrorHandler:
    def test_handle_timeout(self):
        error = Exception("timeout occurred")
        result = handle_ai_service_error(error, "analysis")
        assert result["fallback"] is True
        assert result["error_type"] == "timeout"
        assert "timeout" in result["message"].lower()
    
    def test_handle_unavailable(self):
        error = Exception("Service unavailable 503")
        result = handle_ai_service_error(error, "analysis")
        assert result["fallback"] is True
        assert result["error_type"] == "unavailable"
    
    def test_handle_generic_error(self):
        error = Exception("Unknown AI error")
        result = handle_ai_service_error(error, "analysis")
        assert result["fallback"] is True
        assert result["error_type"] == "error"


class TestDatabaseErrorHandler:
    def test_handle_duplicate_error(self):
        error = Exception("Duplicate entry for key 'email'")
        result = handle_database_error(error, "creating user")
        assert isinstance(result, HTTPException)
        assert result.status_code == 409
        assert "already exists" in result.detail
    
    def test_handle_foreign_key_error(self):
        error = Exception("foreign key constraint failed")
        result = handle_database_error(error, "creating record")
        assert isinstance(result, HTTPException)
        assert result.status_code == 400
    
    def test_handle_connection_error(self):
        error = Exception("connection refused")
        result = handle_database_error(error, "query")
        assert isinstance(result, HTTPException)
        assert result.status_code == 503


class TestEdgeCases:
    def test_boundary_values(self):
        # Exactly at boundary
        validate_password("123456")  # Min 6 chars
        validate_string_field("AB", "Field", min_length=2, max_length=2)
        validate_integer_field(1, "Count", min_value=1, max_value=1)
    
    def test_unicode_and_special_chars(self):
        email = validate_email("test+tag@example.co.uk")
        assert "@" in email
        
        result = validate_string_field("Title with émojis 🎉", "Title", max_length=100)
        assert "🎉" in result
    
    def test_whitespace_handling(self):
        # Should trim whitespace
        result = validate_string_field("   spaced   ", "Field")
        assert result == "spaced"
        
        # Empty after trimming
        with pytest.raises(HTTPException):
            validate_string_field("   ", "Field", required=True)
    
    def test_case_insensitivity(self):
        assert validate_email("TeSt@ExAmPlE.cOm") == "test@example.com"
        assert validate_role("RECRUITER") == "recruiter"
        assert validate_job_status("ACTIVE") == "active"
