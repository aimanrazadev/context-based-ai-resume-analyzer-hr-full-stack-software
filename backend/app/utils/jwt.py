from datetime import datetime, timedelta
from jose import jwt

from ..config import SECRET_KEY

ALGORITHM = "HS256"
# Dev-friendly default (prevents users getting randomly logged out during testing).
# If you want shorter sessions later, reduce this and add refresh tokens.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
