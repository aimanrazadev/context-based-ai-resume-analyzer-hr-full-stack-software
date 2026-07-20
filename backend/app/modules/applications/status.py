import re

DEFAULT_APPLICATION_STATUS = "not-reviewed"
ALLOWED_APPLICATION_STATUSES = {"not-reviewed", "shortlisted", "on-hold", "rejected"}
_LEGACY_APPLICATION_STATUS_ALIASES = {
    "submitted": DEFAULT_APPLICATION_STATUS,
    "accepted": DEFAULT_APPLICATION_STATUS,
    "applied": DEFAULT_APPLICATION_STATUS,
    "pending": DEFAULT_APPLICATION_STATUS,
    "hold": "on-hold",
    "onhold": "on-hold",
}


def _status_token(status: str | None) -> str:
    return re.sub(r"[\s_]+", "-", (status or "").strip().lower())


def normalize_application_status(status: str | None) -> str:
    value = _status_token(status)
    if not value:
        return DEFAULT_APPLICATION_STATUS
    if value in _LEGACY_APPLICATION_STATUS_ALIASES:
        return _LEGACY_APPLICATION_STATUS_ALIASES[value]
    return value if value in ALLOWED_APPLICATION_STATUSES else DEFAULT_APPLICATION_STATUS


def validate_application_status(status: str | None) -> str:
    value = _status_token(status)
    if value in _LEGACY_APPLICATION_STATUS_ALIASES:
        return _LEGACY_APPLICATION_STATUS_ALIASES[value]
    if value in ALLOWED_APPLICATION_STATUSES:
        return value
    raise ValueError("Invalid application status. Use not-reviewed, shortlisted, on-hold, or rejected.")
