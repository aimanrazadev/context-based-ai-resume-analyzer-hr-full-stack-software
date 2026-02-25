import bcrypt


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt directly (bypasses passlib+version issues).

    bcrypt truncates at 72 *bytes* and this build raises if you exceed it,
    so enforce the limit explicitly.
    """
    if not password:
        raise ValueError("Password is required")

    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError("Password must be 72 bytes or less")

    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        if not password or not hashed:
            return False
        pw_bytes = password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False
