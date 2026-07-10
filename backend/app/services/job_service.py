import json


def normalize_required_skills(raw: str | list[str] | None) -> list[str]:
    """Return only the recruiter's explicit, deduplicated required skills."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            values = parsed if isinstance(parsed, list) else raw.split(",")
        except json.JSONDecodeError:
            values = raw.split(",")
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        skill = str(value).strip()
        key = skill.casefold()
        if skill and key not in seen:
            seen.add(key)
            result.append(skill)
    return result
