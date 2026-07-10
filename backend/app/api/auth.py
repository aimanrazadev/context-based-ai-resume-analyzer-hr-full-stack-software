from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.auth import LoginRequest, SignupRequest
from ..services.auth_service import login_user, signup_user

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    return signup_user(db, email=payload.email, password=payload.password, role=payload.role, name=payload.name)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return login_user(db, email=payload.email, password=payload.password, role=payload.role)


@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}
