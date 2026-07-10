from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.candidate import Candidate
from ..models.user import User
from ..utils.error_handlers import get_error_message, handle_database_error
from ..utils.jwt import create_access_token
from ..utils.security import hash_password, verify_password
from ..utils.validation import validate_email, validate_password, validate_role


def signup_user(db: Session, *, email: str, password: str, role: str, name: str | None) -> dict:
    email = validate_email(email)
    validate_password(password)
    role = validate_role(role)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.role == role:
            raise HTTPException(
                status_code=400,
                detail="An account is already registered with this email. Please login instead.",
            )
        existing_role = str(existing.role or "user").capitalize()
        raise HTTPException(
            status_code=400,
            detail=f"This email is already registered as a {existing_role}. Please sign up using a different email address.",
        )
    user = User(name=name, email=email, password=hash_password(password), role=role)
    try:
        db.add(user)
        db.flush()
        if role == "candidate" and not db.query(Candidate).filter(Candidate.email == email).first():
            db.add(Candidate(name=name or email.split("@", 1)[0], email=email))
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise handle_database_error(exc, "creating user")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"message": "User created successfully", "user": {"id": user.id, "email": user.email, "role": user.role}, "access_token": token, "token_type": "bearer"}


def login_user(db: Session, *, email: str, password: str, role: str | None) -> dict:
    email = validate_email(email)
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email.")
    if role and user.role != role:
        existing_role = str(user.role or "user").capitalize()
        raise HTTPException(status_code=403, detail=f"This email is registered as a {existing_role}. Please select the correct account type.")
    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "role": user.role}}
