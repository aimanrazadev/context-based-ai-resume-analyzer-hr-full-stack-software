import json
from typing import Any


def safe_json_loads(
    value: str | None,
    *,
    default: Any = None,
    expected_type: type | tuple[type, ...] | None = None,
) -> Any:
    if not value:
        return default

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default

    if expected_type and not isinstance(parsed, expected_type):
        return default

    return parsed
