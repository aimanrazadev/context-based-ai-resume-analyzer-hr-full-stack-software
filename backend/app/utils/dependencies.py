from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from ..config import SECRET_KEY
from ..database import get_db
from ..models.user import User
from .jwt import ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_ALLOWED_ROLES = {"candidate", "recruiter"}


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    role = str(payload.get("role") or "").strip().lower()
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token") from None
    if role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or str(user.role or "").strip().lower() != role:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"sub": str(user.id), "role": role, "email": user.email, "name": user.name}
