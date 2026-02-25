import json
import re
from typing import Any


_WORD_RE = re.compile(r"[A-Za-z0-9+#.]{2,}")
_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}

_SKILL_ALIASES = {
    "fastapi": "python",
    "django": "python",
    "flask": "python",
    "pandas": "python",
    "numpy": "python",
    "spring": "java",
    "springboot": "java",
    "node": "javascript",
    "nodejs": "javascript",
    "reactjs": "react",
    "nextjs": "react",
    "typescript": "javascript",
    "postgresql": "sql",
    "mysql": "sql",
    "sqlite": "sql",
    "rest": "api",
    "restapi": "api",
    "microservices": "backend",
    "microservice": "backend",
}


def _normalize_skill(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9+#. ]+", " ", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s


def _canonical_skill(s: str) -> str:
    n = _normalize_skill(s)
    key = n.replace(" ", "")
    return _SKILL_ALIASES.get(key, _SKILL_ALIASES.get(n, n))


def extract_resume_skills(*, structured_json: str | None, ai_structured_json: str | None = None) -> list[str]:
    """
    Returns normalized skill tokens from Module 7/8 structured payloads.
    Prefer deterministic structured_json, fall back to ai_structured_json.
    """
    raw = structured_json or ai_structured_json or ""
    if not raw:
        return []
    try:
        payload: Any = json.loads(raw)
    except Exception:
        return []
    items = (
        (((payload or {}).get("sections") or {}).get("skills") or {}).get("items")
        or []
    )
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        n = _canonical_skill(str(it))
        if not n:
            continue
        # Keep phrase + individual tokens (improves overlap with job tokenization)
        candidates = [n]
        if " " in n:
            candidates.extend([p for p in n.split(" ") if p])
        for c in candidates:
            if not c:
                continue
            if c in seen:
                continue
            seen.add(c)
            out.append(c)
    return out


def extract_job_skill_tokens(
    *,
    job_title: str | None,
    job_description: str | None,
    required_skills: list[str] | None = None,
) -> list[str]:
    """
    Very lightweight skill-token extraction from job text.
    Intended for deterministic overlap scoring, not perfect NLP.
    """
    explicit = [
        _canonical_skill(str(s))
        for s in (required_skills or [])
        if _canonical_skill(str(s))
    ]
    if explicit:
        seen_explicit: set[str] = set()
        out_explicit: list[str] = []
        for skill in explicit:
            if skill in seen_explicit:
                continue
            seen_explicit.add(skill)
            out_explicit.append(skill)
        return out_explicit[:60]

    text = f"{job_title or ''}\n{job_description or ''}".strip().lower()
    toks: list[str] = []
    seen: set[str] = set()
    for m in _WORD_RE.finditer(text):
        w = m.group(0).strip(".")
        if not w or w in _STOP:
            continue
        if len(w) > 40:
            continue
        w = _canonical_skill(w)
        if w in seen:
            continue
        seen.add(w)
        toks.append(w)
    # Prevent dilution: keep a reasonable cap so overlap isn't always ~0.
    return toks[:60]


def skills_overlap_score(*, resume_skills: list[str], job_skills: list[str]) -> tuple[float, list[str], list[str]]:
    """
    Recall-style: how many of job skill tokens appear in resume skills.
    Returns (skills_score in [0,1], matched_skills, missing_skills)
    """
    rs = set(resume_skills or [])
    js = list(job_skills or [])
    if not js:
        return 0.0, [], []
    matched = [j for j in js if j in rs]
    missing = [j for j in js if j not in rs]
    # F1-style balance between "job covered by resume" and "resume aligned to job"
    recall = len(matched) / max(1, len(js))
    precision = len(matched) / max(1, len(rs)) if rs else 0.0
    if (precision + recall) <= 0.0:
        score = 0.0
    else:
        score = (2.0 * precision * recall) / (precision + recall)
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return float(score), matched[:12], missing[:8]


def extract_resume_experience_text(*, structured_json: str | None, ai_structured_json: str | None = None) -> str:
    """
    Extract a best-effort experience text blob from structured payloads.
    Prefer deterministic structured_json, fall back to ai_structured_json.
    """
    raw = structured_json or ai_structured_json or ""
    if not raw:
        return ""
    try:
        payload: Any = json.loads(raw)
    except Exception:
        return ""

    exp = (((payload or {}).get("sections") or {}).get("experience") or {})
    txt = str(exp.get("text") or "")
    items = exp.get("items") or []
    if isinstance(items, list) and items:
        txt = (txt + "\n" + "\n".join([str(x) for x in items if x is not None])).strip()
    return txt.strip()


def extract_resume_education_text(*, structured_json: str | None, ai_structured_json: str | None = None) -> str:
    raw = structured_json or ai_structured_json or ""
    if not raw:
        return ""
    try:
        payload: Any = json.loads(raw)
    except Exception:
        return ""

    edu = (((payload or {}).get("sections") or {}).get("education") or {})
    txt = str(edu.get("text") or "")
    items = edu.get("items") or []
    if isinstance(items, list) and items:
        txt = (txt + "\n" + "\n".join([str(x) for x in items if x is not None])).strip()
    return txt.strip()


def experience_relevance_score(*, job_tokens: list[str], experience_text: str) -> float:
    """
    Deterministic experience relevance in [0,1].
    Uses token overlap with job tokens + a light length signal so empty experience doesn't score well.
    """
    et = (experience_text or "").lower().strip()
    if not et or not job_tokens:
        return 0.0

    exp_tokens: set[str] = set()
    for m in _WORD_RE.finditer(et):
        w = m.group(0).strip(".")
        if not w or w in _STOP:
            continue
        exp_tokens.add(w)
        if len(exp_tokens) >= 800:
            break

    if not exp_tokens:
        return 0.0

    overlap = sum(1 for t in job_tokens if t in exp_tokens)
    overlap_ratio = overlap / max(1, len(job_tokens))

    # Length factor: ~0 for very short experience text, approaches 1 by ~900 chars.
    length_factor = min(1.0, max(0.0, len(et) / 900.0))

    score = 0.7 * overlap_ratio + 0.3 * length_factor
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return float(score)


def education_relevance_score(*, job_title: str | None, job_description: str | None, education_text: str) -> float:
    txt = (education_text or "").lower().strip()
    if not txt:
        return 0.0

    degree_hits = 0
    for kw in ("b.tech", "btech", "b.e", "be ", "bachelor", "m.tech", "mtech", "master", "computer science", "engineering"):
        if kw in txt:
            degree_hits += 1

    cert_hits = 0
    for kw in ("certification", "certified", "course", "bootcamp", "specialization"):
        if kw in txt:
            cert_hits += 1

    job_text = f"{job_title or ''} {job_description or ''}".lower()
    stem_overlap = 0
    for stem in ("backend", "api", "cloud", "data", "python", "java", "javascript", "sql", "devops"):
        if stem in txt and stem in job_text:
            stem_overlap += 1

    score = 0.35 * min(1.0, degree_hits / 3.0) + 0.15 * min(1.0, cert_hits / 2.0) + 0.50 * min(1.0, stem_overlap / 4.0)
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return float(score)


def compute_final_score(
    *,
    semantic_score: float,
    skills_score: float,
    experience_score: float,
    education_score: float,
    ai_reasoning_score: float,
) -> int:
    semantic_score = float(semantic_score or 0.0)
    skills_score = float(skills_score or 0.0)
    experience_score = float(experience_score or 0.0)
    education_score = float(education_score or 0.0)
    ai_reasoning_score = float(ai_reasoning_score or 0.0)
    if semantic_score < 0.0:
        semantic_score = 0.0
    if semantic_score > 1.0:
        semantic_score = 1.0
    if skills_score < 0.0:
        skills_score = 0.0
    if skills_score > 1.0:
        skills_score = 1.0
    if experience_score < 0.0:
        experience_score = 0.0
    if experience_score > 1.0:
        experience_score = 1.0
    if education_score < 0.0:
        education_score = 0.0
    if education_score > 1.0:
        education_score = 1.0
    if ai_reasoning_score < 0.0:
        ai_reasoning_score = 0.0
    if ai_reasoning_score > 1.0:
        ai_reasoning_score = 1.0

    val = 100.0 * (
        0.10 * semantic_score
        + 0.20 * skills_score
        + 0.15 * experience_score
        + 0.10 * education_score
        + 0.45 * ai_reasoning_score
    )
    out = int(round(val))
    if out < 0:
        return 0
    if out > 100:
        return 100
    return out


def score_application(
    *,
    job_title: str | None,
    job_description: str | None,
    job_required_skills: list[str] | None,
    resume_structured_json: str | None,
    resume_ai_structured_json: str | None,
    semantic_score: float,
    ai_relevance_pct: int | None = None,
) -> tuple[float, int, dict[str, Any]]:
    """
    Returns (skills_score, final_score_0_100, breakdown_dict).
    """
    resume_skills = extract_resume_skills(
        structured_json=resume_structured_json,
        ai_structured_json=resume_ai_structured_json,
    )
    job_skills = extract_job_skill_tokens(
        job_title=job_title,
        job_description=job_description,
        required_skills=job_required_skills,
    )
    skills_score, matched, missing = skills_overlap_score(resume_skills=resume_skills, job_skills=job_skills)

    exp_text = extract_resume_experience_text(
        structured_json=resume_structured_json,
        ai_structured_json=resume_ai_structured_json,
    )
    experience_score = experience_relevance_score(job_tokens=job_skills, experience_text=exp_text)

    edu_text = extract_resume_education_text(
        structured_json=resume_structured_json,
        ai_structured_json=resume_ai_structured_json,
    )
    education_score = education_relevance_score(
        job_title=job_title,
        job_description=job_description,
        education_text=edu_text,
    )

    ai_score = None
    try:
        if ai_relevance_pct is not None:
            ai_score = max(0, min(100, int(ai_relevance_pct)))
    except Exception:
        ai_score = None
    ai_reasoning_score = float(ai_score / 100.0) if isinstance(ai_score, int) else 0.0

    final_score = compute_final_score(
        semantic_score=semantic_score,
        skills_score=skills_score,
        experience_score=experience_score,
        education_score=education_score,
        ai_reasoning_score=ai_reasoning_score,
    )

    notes: list[str] = []
    if not resume_structured_json and not resume_ai_structured_json:
        notes.append("No structured resume skills available; skills_score may be low.")
    if not job_skills:
        notes.append("Could not extract skill tokens from job description.")
    if ai_score is None:
        notes.append("No AI reasoning score available; ai_reasoning_score set to 0.")

    breakdown: dict[str, Any] = {
        # Keep semantic/skills keys for backwards compatibility with UI/tests.
        "weights": {"ai_reasoning": 0.45, "skills": 0.20, "experience": 0.15, "education": 0.10, "semantic": 0.10},
        "semantic_score": float(semantic_score),
        "skills_score": float(skills_score),
        "experience_score": float(experience_score),
        "education_score": float(education_score),
        "ai_reasoning_score": float(ai_reasoning_score),
        "ai_relevance_score": float(ai_reasoning_score),
        "matched_skills": matched,
        "missing_skills": missing,
        "notes": notes,
    }
    return float(skills_score), int(final_score), breakdown

