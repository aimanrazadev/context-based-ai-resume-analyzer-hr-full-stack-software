import json
import re
from typing import Any


SKILL_ALIASES = {
    "api": "api",
    "apis": "api",
    "fast api": "fastapi",
    "fastapi": "fastapi",
    "gemini": "gemini",
    "gemini api": "gemini",
    "javascript": "javascript",
    "js": "javascript",
    "large language model": "llm",
    "large language models": "llm",
    "largelanguagemodels": "llm",
    "llm": "llm",
    "llm integration": "llm",
    "llms": "llm",
    "machine learning": "machine learning",
    "machinelearning": "machine learning",
    "ml": "machine learning",
    "mysql": "sql",
    "natural language processing": "nlp",
    "naturallanguageprocessing": "nlp",
    "nextjs": "next.js",
    "nlp": "nlp",
    "node": "node.js",
    "node.js": "node.js",
    "nodejs": "node.js",
    "num py": "numpy",
    "numpy": "numpy",
    "openai": "openai",
    "openai api": "openai",
    "pandas": "pandas",
    "postgres": "sql",
    "postgresql": "sql",
    "prompt engineering": "prompt engineering",
    "pymu pdf": "pymupdf",
    "pymupdf": "pymupdf",
    "python docx": "python-docx",
    "python-docx": "python-docx",
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "rest": "api",
    "rest api": "api",
    "rest apis": "api",
    "restapi": "api",
    "restapis": "api",
    "restful api": "api",
    "restful apis": "api",
    "scikit learn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "scikitlearn": "scikit-learn",
    "semantic search": "semantic search",
    "semantic similarity": "semantic search",
    "sklearn": "scikit-learn",
    "sql": "sql",
    "sqlite": "sql",
    "transformer embeddings": "embeddings",
}


def normalize_skill(skill: str | None) -> str:
    value = (skill or "").strip().lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9+#. ]+", " ", value).strip()
    return re.sub(r"\s{2,}", " ", value)


def canonical_skill(skill: str | None) -> str:
    normalized = normalize_skill(skill)
    compact = re.sub(r"[^a-z0-9+#.]+", "", normalized)
    return SKILL_ALIASES.get(compact, SKILL_ALIASES.get(normalized, normalized))


def skill_aliases(skill: str | None) -> set[str]:
    normalized = normalize_skill(skill)
    canonical = canonical_skill(skill)
    compact = re.sub(r"[^a-z0-9+#.]+", "", normalized)
    aliases = {normalized, compact, canonical}
    aliases.update(
        alias for alias, target in SKILL_ALIASES.items() if target == canonical
    )
    return {alias for alias in aliases if alias}


def contains_skill(text: str | None, skill: str | None) -> bool:
    haystack = (text or "").lower()
    compact_haystack = re.sub(r"[^a-z0-9+#.]+", "", haystack)
    for alias in skill_aliases(skill):
        if " " in alias or "-" in alias or "." in alias or "+" in alias or "#" in alias:
            pattern = re.escape(alias).replace("\\ ", r"\s+").replace("\\-", r"[-\s]?")
            if re.search(rf"(^|[^a-z0-9+#.]){pattern}([^a-z0-9+#.]|$)", haystack):
                return True
        elif alias in compact_haystack:
            return True
    return False


def deduplicate_skills(skills: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for skill in skills or []:
        label = re.sub(r"\s+", " ", str(skill or "")).strip()
        key = canonical_skill(label)
        if not label or key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def normalize_required_skills(raw: str | list[str] | None) -> list[str]:
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
    return deduplicate_skills([str(value) for value in values])


def classify_required_skills(*, text: str, required_skills: list[str] | None) -> dict[str, list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    for skill in deduplicate_skills(required_skills):
        if contains_skill(text, skill):
            matched.append(skill)
        else:
            missing.append(skill)
    return {"matched_skills": matched, "missing_skills": missing}
