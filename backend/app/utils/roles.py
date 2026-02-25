from fastapi import Depends, HTTPException
from .dependencies import get_current_user


def _role_required(required_role: str):
    def check_role(user=Depends(get_current_user)):
        if user.get("role") != required_role:
            raise HTTPException(status_code=403, detail=f"{required_role.capitalize()} access only")
        return user
    return check_role


recruiter_only = _role_required("recruiter")
candidate_only = _role_required("candidate")