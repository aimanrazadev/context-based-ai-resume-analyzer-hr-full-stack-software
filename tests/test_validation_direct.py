"""
Direct validation tests without pytest
Run with: python test_validation_direct.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.utils.validation import (
    validate_email,
    validate_password,
    validate_string_field,
    validate_integer_field,
    validate_role,
    validate_job_status,
    sanitize_filename,
)
from fastapi import HTTPException

def run_test_function(name, func):
    try:
        func()
        print(f"[PASS] {name}")
        return True
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] {name}: Unexpected error: {e}")
        return False

# Test cases
tests_passed = 0
tests_failed = 0

def test_valid_email():
    email = validate_email("test@example.com")
    assert email == "test@example.com"
    email2 = validate_email("  TEST@EXAMPLE.COM  ")
    assert email2 == "test@example.com"

def test_invalid_email():
    try:
        validate_email("invalid")
        raise AssertionError("Should have raised HTTPException")
    except HTTPException as e:
        assert e.status_code == 400

def test_valid_password():
    validate_password("password123")
    validate_password("123456")  # Minimum

def test_weak_password():
    try:
        validate_password("12345")
        raise AssertionError("Should have raised HTTPException")
    except HTTPException as e:
        assert e.status_code == 400

def test_string_validation():
    result = validate_string_field("Test", "Field", min_length=2, max_length=50)
    assert result == "Test"
    
    # Test trimming
    result2 = validate_string_field("  test  ", "Field")
    assert result2 == "test"

def test_string_too_short():
    try:
        validate_string_field("A", "Field", min_length=2)
        raise AssertionError("Should have raised HTTPException")
    except HTTPException as e:
        assert e.status_code == 400

def test_integer_validation():
    result = validate_integer_field(42, "Count", min_value=1, max_value=100)
    assert result == 42
    
    # Test conversion
    result2 = validate_integer_field("42", "Count")
    assert result2 == 42

def test_integer_out_of_range():
    try:
        validate_integer_field(0, "Count", min_value=1)
        raise AssertionError("Should have raised HTTPException")
    except HTTPException as e:
        assert e.status_code == 400

def test_role_validation():
    assert validate_role("recruiter") == "recruiter"
    assert validate_role("CANDIDATE") == "candidate"
    assert validate_role("admin") == "admin"

def test_invalid_role():
    try:
        validate_role("invalid")
        raise AssertionError("Should have raised HTTPException")
    except HTTPException as e:
        assert e.status_code == 400

def test_job_status():
    assert validate_job_status("active") == "active"
    assert validate_job_status("DRAFT") == "draft"
    assert validate_job_status(None) == "active"

def test_filename_sanitization():
    assert sanitize_filename("resume.pdf") == "resume.pdf"
    
    # Test directory traversal removal
    result = sanitize_filename("../../etc/passwd.pdf")
    assert ".." not in result
    assert "/" not in result

def test_malicious_filename():
    result = sanitize_filename("path/to/file.pdf")
    assert "/" not in result
    
    result2 = sanitize_filename(".hidden.pdf")
    assert not result2.startswith(".")

if __name__ == "__main__":
    # Run all tests
    tests = [
        ("Valid email normalization", test_valid_email),
        ("Invalid email rejection", test_invalid_email),
        ("Valid password acceptance", test_valid_password),
        ("Weak password rejection", test_weak_password),
        ("String field validation", test_string_validation),
        ("String too short rejection", test_string_too_short),
        ("Integer field validation", test_integer_validation),
        ("Integer out of range rejection", test_integer_out_of_range),
        ("Role validation", test_role_validation),
        ("Invalid role rejection", test_invalid_role),
        ("Job status validation", test_job_status),
        ("Filename sanitization", test_filename_sanitization),
        ("Malicious filename sanitization", test_malicious_filename),
    ]

    print("\n" + "="*60)
    print("MODULE 13 - VALIDATION TESTS")
    print("="*60 + "\n")
    # Set UTF-8 encoding for output
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    for name, test in tests:
        if run_test_function(name, test):
            tests_passed += 1
        else:
            tests_failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("="*60 + "\n")

    if tests_failed == 0:
        print("[SUCCESS] All validation tests passed!")
        sys.exit(0)
    else:
        print("[ERROR] Some tests failed")
        sys.exit(1)
