"""
Deterministic application scoring utilities.

This module is responsible for:
- extracting reusable structured signals from parsed resume payloads
- computing deterministic skills, experience, projects, and education scores
- combining semantic and AI-derived signals into a final 0-100 score
- returning recruiter-friendly breakdown data for ranking transparency
"""

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
    """
    Normalize a raw skill token before canonical mapping.

    Args:
        s: Raw skill or keyword text.

    Returns:
        A lowercased normalized token string.

    Side Effects:
        None.

    Error Handling:
        Treats falsy inputs as empty strings.
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9+#. ]+", " ", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s


def _canonical_skill(s: str) -> str:
    """
    Map a normalized skill token to a lightweight canonical representation.

    Args:
        s: Raw or normalized skill text.

    Returns:
        A canonical token used for overlap scoring.

    Side Effects:
        None.

    Error Handling:
        Falls back to the normalized input when no alias mapping exists.
    """
    n = _normalize_skill(s)
    key = n.replace(" ", "")
    return _SKILL_ALIASES.get(key, _SKILL_ALIASES.get(n, n))


def extract_resume_skills(*, structured_json: str | None, ai_structured_json: str | None = None) -> list[str]:
    """
    Extract normalized skills from deterministic or AI-structured resume payloads.

    Args:
        structured_json: Deterministic structured resume JSON.
        ai_structured_json: AI-structured resume JSON fallback.

    Returns:
        A deduplicated list of canonical skill tokens and phrases.

    Side Effects:
        None.

    Error Handling:
        Returns an empty list when the payload is missing, malformed, or does
        not contain a skills item list.
    """
    raw = structured_json or ai_structured_json or ""
    if not raw:
        return []
    try:
        payload: Any = json.loads(raw)
    except Exception:
        return []
    items = ((((payload or {}).get("sections") or {}).get("skills") or {}).get("items") or [])
    if not isinstance(items, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        n = _canonical_skill(str(it))
        if not n:
            continue
        candidates = [n]
        if " " in n:
            candidates.extend([p for p in n.split(" ") if p])
        for c in candidates:
            if not c or c in seen:
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
    Extract lightweight canonical skill tokens from job content.

    Args:
        job_title: Job title text.
        job_description: Job description text.
        required_skills: Optional explicit required skills list.

    Returns:
        A capped list of canonical job skill tokens.

    Side Effects:
        None.

    Error Handling:
        Returns an empty list when no usable job skill signal exists.
    """
    explicit = [_canonical_skill(str(s)) for s in (required_skills or []) if _canonical_skill(str(s))]
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
        if not w or w in _STOP or len(w) > 40:
            continue
        w = _canonical_skill(w)
        if w in seen:
            continue
        seen.add(w)
        toks.append(w)
    return toks[:60]


def skills_overlap_score(*, resume_skills: list[str], job_skills: list[str]) -> tuple[float, list[str], list[str]]:
    """
    Compute a balanced skill-overlap score between resume and job skill tokens.

    Args:
        resume_skills: Canonical resume skills.
        job_skills: Canonical job skill tokens.

    Returns:
        A tuple of:
        - score in [0, 1]
        - matched skills
        - missing skills

    Side Effects:
        None.

    Error Handling:
        Returns a zero score when no job skill tokens are available.
    """
    rs = set(resume_skills or [])
    js = list(job_skills or [])
    if not js:
        return 0.0, [], []
    matched = [j for j in js if j in rs]
    missing = [j for j in js if j not in rs]
    recall = len(matched) / max(1, len(js))
    precision = len(matched) / max(1, len(rs)) if rs else 0.0
    if (precision + recall) <= 0.0:
        score = 0.0
    else:
        score = (2.0 * precision * recall) / (precision + recall)
    return float(max(0.0, min(1.0, score))), matched[:12], missing[:8]


def extract_resume_experience_text(*, structured_json: str | None, ai_structured_json: str | None = None) -> str:
    """
    Extract a best-effort experience text blob from resume payloads.

    Args:
        structured_json: Deterministic structured resume JSON.
        ai_structured_json: AI-structured resume JSON fallback.

    Returns:
        A single combined experience text string.

    Side Effects:
        None.

    Error Handling:
        Returns an empty string when parsing fails or experience is missing.
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
        rendered = [str(x.get("summary") if isinstance(x, dict) else x) for x in items if x is not None]
        txt = (txt + "\n" + "\n".join(rendered)).strip()
    return txt.strip()


def extract_resume_projects_text(*, structured_json: str | None, ai_structured_json: str | None = None) -> str:
    """
    Extract a best-effort projects text blob from resume payloads.

    Args:
        structured_json: Deterministic structured resume JSON.
        ai_structured_json: AI-structured resume JSON fallback.

    Returns:
        A single combined projects text string.

    Side Effects:
        None.

    Error Handling:
        Returns an empty string when parsing fails or projects are missing.
    """
    raw = structured_json or ai_structured_json or ""
    if not raw:
        return ""
    try:
        payload: Any = json.loads(raw)
    except Exception:
        return ""

    proj = (((payload or {}).get("sections") or {}).get("projects") or {})
    txt = str(proj.get("text") or "")
    items = proj.get("items") or []
    if isinstance(items, list) and items:
        rendered = [str(x.get("summary") if isinstance(x, dict) else x) for x in items if x is not None]
        txt = (txt + "\n" + "\n".join(rendered)).strip()
    return txt.strip()


def extract_resume_education_text(*, structured_json: str | None, ai_structured_json: str | None = None) -> str:
    """
    Extract a best-effort education text blob from resume payloads.

    Args:
        structured_json: Deterministic structured resume JSON.
        ai_structured_json: AI-structured resume JSON fallback.

    Returns:
        A single combined education text string.

    Side Effects:
        None.

    Error Handling:
        Returns an empty string when parsing fails or education is missing.
    """
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
        rendered = [str(x.get("summary") if isinstance(x, dict) else x) for x in items if x is not None]
        txt = (txt + "\n" + "\n".join(rendered)).strip()
    return txt.strip()


def experience_relevance_score(*, job_tokens: list[str], experience_text: str) -> float:
    """
    Score how relevant the experience section is to the job skill tokens.

    Args:
        job_tokens: Canonical job tokens.
        experience_text: Combined experience text from the resume.

    Returns:
        A score in the range [0, 1].

    Side Effects:
        None.

    Error Handling:
        Returns 0.0 when either input is too weak to score.
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
    length_factor = min(1.0, max(0.0, len(et) / 900.0))
    score = 0.7 * overlap_ratio + 0.3 * length_factor
    return float(max(0.0, min(1.0, score)))


def projects_relevance_score(*, job_tokens: list[str], projects_text: str) -> float:
    """
    Score how relevant the projects section is to the job skill tokens.

    Args:
        job_tokens: Canonical job tokens.
        projects_text: Combined projects text from the resume.

    Returns:
        A score in the range [0, 1].

    Side Effects:
        None.

    Error Handling:
        Returns 0.0 when either input is too weak to score.
    """
    pt = (projects_text or "").lower().strip()
    if not pt or not job_tokens:
        return 0.0

    project_tokens: set[str] = set()
    for m in _WORD_RE.finditer(pt):
        w = m.group(0).strip(".")
        if not w or w in _STOP:
            continue
        project_tokens.add(w)
        if len(project_tokens) >= 700:
            break

    if not project_tokens:
        return 0.0

    overlap = sum(1 for t in job_tokens if t in project_tokens)
    overlap_ratio = overlap / max(1, len(job_tokens))
    length_factor = min(1.0, max(0.0, len(pt) / 700.0))
    score = 0.75 * overlap_ratio + 0.25 * length_factor
    return float(max(0.0, min(1.0, score)))


def education_relevance_score(*, job_title: str | None, job_description: str | None, education_text: str) -> float:
    """
    Score how relevant education signals are to the target job.

    Args:
        job_title: Job title text.
        job_description: Job description text.
        education_text: Combined education text from the resume.

    Returns:
        A score in the range [0, 1].

    Side Effects:
        None.

    Error Handling:
        Returns 0.0 when education text is empty.
    """
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
    return float(max(0.0, min(1.0, score)))


def compute_final_score(
    *,
    semantic_score: float,
    skills_score: float,
    experience_score: float,
    projects_score: float,
    education_score: float,
    ai_reasoning_score: float,
) -> int:
    """
    Combine normalized component scores into one final application score.

    Args:
        semantic_score: Embedding or fallback semantic score in [0, 1].
        skills_score: Skill overlap score in [0, 1].
        experience_score: Experience relevance score in [0, 1].
        projects_score: Projects relevance score in [0, 1].
        education_score: Education relevance score in [0, 1].
        ai_reasoning_score: AI relevance score in [0, 1].

    Returns:
        A rounded integer final score in the range [0, 100].

    Side Effects:
        None.

    Error Handling:
        Clamps each incoming component into [0, 1] before aggregation.
    """
    semantic_score = max(0.0, min(1.0, float(semantic_score or 0.0)))
    skills_score = max(0.0, min(1.0, float(skills_score or 0.0)))
    experience_score = max(0.0, min(1.0, float(experience_score or 0.0)))
    projects_score = max(0.0, min(1.0, float(projects_score or 0.0)))
    education_score = max(0.0, min(1.0, float(education_score or 0.0)))
    ai_reasoning_score = max(0.0, min(1.0, float(ai_reasoning_score or 0.0)))

    weights = {
        "ai_reasoning": 0.40,
        "skills": 0.20,
        "experience": 0.12,
        "projects": 0.08,
        "education": 0.10,
        "semantic": 0.10,
    }
    val = 100.0 * (
        weights["semantic"] * semantic_score
        + weights["skills"] * skills_score
        + weights["experience"] * experience_score
        + weights["projects"] * projects_score
        + weights["education"] * education_score
        + weights["ai_reasoning"] * ai_reasoning_score
    )
    out = int(round(val))
    return max(0, min(100, out))


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
    Compute the final application score and a recruiter-friendly breakdown.

    Args:
        job_title: Job title text.
        job_description: Job description text.
        job_required_skills: Optional explicit required skills list.
        resume_structured_json: Deterministic structured resume JSON.
        resume_ai_structured_json: AI-structured resume JSON fallback.
        semantic_score: Semantic similarity score in [0, 1].
        ai_relevance_pct: Optional AI score in 0-100 integer form.

    Returns:
        A tuple of:
        - skills score in [0, 1]
        - final score in [0, 100]
        - detailed breakdown dictionary

    Side Effects:
        None.

    Error Handling:
        Produces a valid breakdown even when some resume or AI signals are
        missing.
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

    projects_text = extract_resume_projects_text(
        structured_json=resume_structured_json,
        ai_structured_json=resume_ai_structured_json,
    )
    projects_score = projects_relevance_score(job_tokens=job_skills, projects_text=projects_text)

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
        projects_score=projects_score,
        education_score=education_score,
        ai_reasoning_score=ai_reasoning_score,
    )

    notes: list[str] = []
    evidence: list[str] = []
    if not resume_structured_json and not resume_ai_structured_json:
        notes.append("No structured resume data available; deterministic scoring may be limited.")
    if not job_skills:
        notes.append("Could not extract skill tokens from job description.")
    if ai_score is None:
        notes.append("No AI reasoning score available; ai_reasoning_score set to 0.")
    if matched:
        evidence.append("Matched skills: " + ", ".join(matched[:6]))
    if projects_text.strip():
        evidence.append("Projects section contributed to deterministic scoring.")
    if exp_text.strip():
        evidence.append("Experience section contributed to deterministic scoring.")
    if edu_text.strip():
        evidence.append("Education section contributed to deterministic scoring.")

    weights = {
        "ai_reasoning": 0.40,
        "skills": 0.20,
        "experience": 0.12,
        "projects": 0.08,
        "education": 0.10,
        "semantic": 0.10,
    }
    component_scores = {
        "semantic_score": float(semantic_score),
        "skills_score": float(skills_score),
        "experience_score": float(experience_score),
        "projects_score": float(projects_score),
        "education_score": float(education_score),
        "ai_reasoning_score": float(ai_reasoning_score),
    }
    weighted_contributions = {
        "semantic": round(100.0 * weights["semantic"] * component_scores["semantic_score"], 2),
        "skills": round(100.0 * weights["skills"] * component_scores["skills_score"], 2),
        "experience": round(100.0 * weights["experience"] * component_scores["experience_score"], 2),
        "projects": round(100.0 * weights["projects"] * component_scores["projects_score"], 2),
        "education": round(100.0 * weights["education"] * component_scores["education_score"], 2),
        "ai_reasoning": round(100.0 * weights["ai_reasoning"] * component_scores["ai_reasoning_score"], 2),
    }

    breakdown: dict[str, Any] = {
        "weights": weights,
        "semantic_score": component_scores["semantic_score"],
        "skills_score": component_scores["skills_score"],
        "experience_score": component_scores["experience_score"],
        "projects_score": component_scores["projects_score"],
        "education_score": component_scores["education_score"],
        "ai_reasoning_score": component_scores["ai_reasoning_score"],
        "ai_relevance_score": component_scores["ai_reasoning_score"],
        "matched_skills": matched,
        "missing_skills": missing,
        "projects_present": bool(projects_text.strip()),
        "experience_present": bool(exp_text.strip()),
        "education_present": bool(edu_text.strip()),
        "weighted_contributions": weighted_contributions,
        "evidence": evidence,
        "notes": notes,
    }
    return float(skills_score), int(final_score), breakdown
