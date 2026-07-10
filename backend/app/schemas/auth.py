from pydantic import BaseModel


class SignupRequest(BaseModel):
    email: str
    password: str
    role: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str | None = None
