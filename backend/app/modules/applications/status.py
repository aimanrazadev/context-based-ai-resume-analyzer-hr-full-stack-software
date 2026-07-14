import re

DEFAULT_APPLICATION_STATUS = "not-reviewed"
ALLOWED_APPLICATION_STATUSES = {"not-reviewed", "shortlisted", "on-hold", "rejected"}


def normalize_application_status(status: str | None) -> str:
    value = re.sub(r"[\s_]+", "-", (status or "").strip().lower())
    if value in {"submitted", "accepted", "applied", "pending"}:
        return DEFAULT_APPLICATION_STATUS
    if value in {"hold", "onhold"}:
        return "on-hold"
    return value if value in ALLOWED_APPLICATION_STATUSES else DEFAULT_APPLICATION_STATUS
