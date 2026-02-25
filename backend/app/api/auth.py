from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import logging

from ..database import get_db
from ..models.candidate import Candidate
from ..models.user import User
from ..utils.jwt import create_access_token
from ..utils.security import hash_password, verify_password
from ..utils.validation import validate_email, validate_password, validate_role
from ..utils.error_handlers import get_error_message, handle_database_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

def _users_role_allows_candidate(db: Session) -> bool:
    """
    MySQL-specific safety check: some existing schemas define users.role as an ENUM
    that doesn't include 'candidate'. For non-MySQL DBs (e.g. SQLite in tests),
    skip this check and allow candidate signups.
    """
    try:
        dialect = getattr(getattr(db, "bind", None), "dialect", None)
        if getattr(dialect, "name", "") and dialect.name != "mysql":
            return True

        row = db.execute(
            text(
                """
                SELECT COLUMN_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'users'
                  AND COLUMN_NAME = 'role'
                """
            )
        ).fetchone()

        column_type = (row[0] if row else "") or ""
        # If it's an enum and doesn't include candidate, we know inserts will fail.
        return not ("enum" in column_type.lower() and "candidate" not in column_type.lower())
    except Exception:
        # Best-effort only.
        return True


class SignupRequest(BaseModel):
    email: str
    password: str
    role: str  # recruiter / candidate
    name: str | None = None  # optional (frontend collects name)


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str | None = None  # optional role gate (frontend-selected role)


@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    # Validate input
    try:
        email = validate_email(payload.email)
        validate_password(payload.password)
        role = validate_role(payload.role)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error in signup: {e}")
        raise HTTPException(status_code=400, detail=get_error_message("validation_error"))
    
    # Check if email already exists
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=get_error_message("email_exists")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error checking existing user: {e}")
        raise handle_database_error(e, "checking existing user")

    # Check DB schema for candidate role
    if role == "candidate" and not _users_role_allows_candidate(db):
        raise HTTPException(
            status_code=503,
            detail=(
                "DB schema does not allow role='candidate' in users.role. "
                "Run: ALTER TABLE users MODIFY COLUMN role "
                "ENUM('admin','recruiter','candidate') NULL DEFAULT 'recruiter'"
            ),
        )

    # Hash password
    try:
        hashed = hash_password(payload.password)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=get_error_message("weak_password")
        )
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise HTTPException(status_code=500, detail=get_error_message("server_error"))

    # Create user
    user = User(
        name=payload.name,
        email=email,
        password=hashed,
        role=role,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating user: {e}")
        raise handle_database_error(e, "creating user")

    # If this is a candidate signup, also ensure a Candidate record exists (used by other tables).
    if role == "candidate":
        try:
            existing_candidate = db.query(Candidate).filter(Candidate.email == email).first()
            if not existing_candidate:
                candidate_name = payload.name or email.split("@", 1)[0]
                candidate = Candidate(name=candidate_name, email=email)
                db.add(candidate)
                db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error creating candidate record: {e}")
            # Don't fail the signup if candidate creation fails
            pass

    # Create access token
    try:
        token = create_access_token({"sub": str(user.id), "role": user.role})
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise HTTPException(status_code=500, detail=get_error_message("server_error"))

    return {
        "message": "User created successfully",
        "user": {"id": user.id, "email": user.email, "role": user.role},
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # Validate input
    try:
        email = validate_email(payload.email)
        if not payload.password:
            raise HTTPException(status_code=400, detail="Password is required")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error in login: {e}")
        raise HTTPException(status_code=400, detail=get_error_message("validation_error"))
    
    # Find user
    try:
        user = db.query(User).filter(User.email == email).first()
    except Exception as e:
        logger.error(f"Database error during login: {e}")
        raise handle_database_error(e, "login")
    
    # Verify credentials
    if not user:
        raise HTTPException(
            status_code=401,
            detail=get_error_message("invalid_credentials")
        )
    
    try:
        if not verify_password(payload.password, user.password):
            raise HTTPException(
                status_code=401,
                detail=get_error_message("invalid_credentials")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        raise HTTPException(status_code=500, detail=get_error_message("server_error"))

    # Check role match if provided
    if payload.role and user.role != payload.role:
        raise HTTPException(
            status_code=403,
            detail="Role mismatch. Please select the correct account type.",
        )

    # Create access token
    try:
        token = create_access_token(
            {"sub": str(user.id), "role": user.role}
        )
    except Exception as e:
        logger.error(f"Token creation error during login: {e}")
        raise HTTPException(status_code=500, detail=get_error_message("server_error"))

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}
