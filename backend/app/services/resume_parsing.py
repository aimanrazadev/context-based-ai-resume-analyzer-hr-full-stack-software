"""
Resume parsing and lightweight structuring utilities.

This module is responsible for:
- detecting common resume section boundaries
- extracting structured text for skills, experience, education, projects, and certifications
- normalizing and deduplicating skill items
- extracting lightweight job title and company name hints
- categorizing skills into technical and soft groups
- validating deterministic parsed output before storage
"""

import re
from typing import Any

from ..schemas.resume_structured import ParsedResumeStructured


_HEADING_ALIASES: dict[str, list[str]] = {
    "skills": ["skills", "technical skills", "key skills", "core skills", "skills & tools", "tools", "technologies", "tech stack"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history", "internships"],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "project experience", "relevant projects"],
    "education": ["education", "academic", "academic background", "education details"],
    "certifications": ["certifications", "certification", "licenses", "licenses & certifications", "education & certifications"],
}

_LINE_CLEAN_RE = re.compile(r"[\t ]{2,}")
_BULLET_LINE_RE = re.compile(r"^\s*[-•\u2022*]\s+")
_SKILL_SPLIT_RE = re.compile(r"[,/|•\u2022;\n]+")
_WORD_SKILL_RE = re.compile(r"[A-Za-z0-9+#.]{2,}")
_DATE_HINT_RE = re.compile(
    r"\b("
    r"\d{4}\s*[-–]\s*(?:\d{4}|present|current|now)"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}"
    r"|present|current"
    r")\b",
    re.IGNORECASE,
)
_DEGREE_HINT_RE = re.compile(
    r"\b("
    r"b\.?tech|m\.?tech|b\.?e|m\.?e|bachelor|master|phd|bsc|msc|diploma|degree|"
    r"certification|certificate|cgpa|gpa|university|college|school"
    r")\b",
    re.IGNORECASE,
)
_PROJECT_HINT_RE = re.compile(
    r"\b(project|developed|built|created|designed|implemented|deployed|github|app|system|platform)\b",
    re.IGNORECASE,
)
_CERT_HINT_RE = re.compile(
    r"\b(certification|certificate|certified|aws|azure|gcp|oracle|scrum|pmp|coursera|udemy|nptel)\b",
    re.IGNORECASE,
)
_SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "collaboration", "problem solving",
    "adaptability", "time management", "critical thinking", "presentation", "mentoring",
}
_TECHNICAL_KEYWORDS = {
    "python", "java", "javascript", "typescript", "react", "next.js", "node.js",
    "sql", "mysql", "postgresql", "mongodb", "aws", "gcp", "docker", "kubernetes",
    "fastapi", "flask", "django", "api", "html", "css", "git", "linux", "nlp", "ml", "ai",
}
_SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "expressjs": "Express.js",
    "express": "Express.js",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sql": "SQL",
    "mysql": "MySQL",
    "api": "API",
    "apis": "APIs",
    "ml": "ML",
    "ai": "AI",
    "aws": "AWS",
    "gcp": "GCP",
    "ci": "CI",
    "cd": "CD",
    "html": "HTML",
    "css": "CSS",
    "nlp": "NLP",
}


def _normalize_line(s: str) -> str:
    """Normalize a single extracted line."""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _LINE_CLEAN_RE.sub(" ", s).strip()
    return s


def _canonical_heading(line: str) -> str | None:
    """Map a heading line to a canonical section key."""
    raw = _normalize_line(line)
    if not raw:
        return None

    key = raw.strip().strip(":").strip("-").strip().lower()
    key = re.sub(r"[^a-z0-9 &]+", "", key).strip()
    if not key:
        return None

    for canonical, aliases in _HEADING_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    return None


def detect_sections(*, text: str) -> dict[str, dict[str, Any]]:
    """Detect section spans by scanning known headings line by line."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        canon = _canonical_heading(line)
        if canon:
            hits.append((i, canon, _normalize_line(line)))

    dedup: list[tuple[int, str, str]] = []
    for i, canon, hline in hits:
        if dedup and dedup[-1][1] == canon and (i - dedup[-1][0]) <= 2:
            continue
        dedup.append((i, canon, hline))

    spans: dict[str, dict[str, Any]] = {}
    for idx, (line_idx, canon, hline) in enumerate(dedup):
        end = len(lines)
        if idx + 1 < len(dedup):
            end = dedup[idx + 1][0]
        spans[canon] = {"start": line_idx + 1, "end": end, "heading_line": hline}
    return spans


def _slice_text(lines: list[str], start: int, end: int) -> str:
    """Slice a line range into a stripped block of text."""
    return "\n".join(lines[start:end]).strip()


def extract_section_texts(*, text: str) -> dict[str, str]:
    """Extract text for the main resume sections."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    spans = detect_sections(text=text)
    out: dict[str, str] = {}
    for sec in ("skills", "experience", "projects", "education", "certifications"):
        meta = spans.get(sec)
        out[sec] = _slice_text(lines, meta["start"], meta["end"]) if meta else ""
    return out


def extract_skill_items(*, skills_text: str, full_text: str) -> list[str]:
    """Extract raw skill phrases from the skills section or full text."""
    base = skills_text.strip() or full_text.strip()
    if not base:
        return []

    cleaned = []
    for line in base.split("\n"):
        l = _normalize_line(line)
        if not l:
            continue
        l = _BULLET_LINE_RE.sub("", l).strip()
        cleaned.append(l)
    blob = "\n".join(cleaned)

    parts = [p.strip() for p in _SKILL_SPLIT_RE.split(blob) if p.strip()]
    tokens: list[str] = []
    for p in parts:
        words = _WORD_SKILL_RE.findall(p)
        if not words:
            continue
        if len(words) <= 3 and len(p) <= 40:
            tokens.append(" ".join(words))
        else:
            tokens.extend(words)
    return tokens


def normalize_skills(*, items: list[str]) -> list[str]:
    """Normalize, alias-map, and deduplicate parsed skill items."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        s = _normalize_line(raw)
        s = s.strip(" -•\u2022").strip()
        if not s:
            continue
        s = re.sub(r"[^A-Za-z0-9+#. ]+", " ", s).strip()
        s = _LINE_CLEAN_RE.sub(" ", s)
        if len(s) < 2 or len(s) > 40:
            continue

        alias_key = s.lower().replace(" ", "")
        if alias_key in _SKILL_ALIASES:
            norm = _SKILL_ALIASES[alias_key]
        elif s.isupper():
            norm = s
        elif re.match(r"^[A-Za-z]{1,6}\d+(\.\d+)?$", s):
            norm = s
        elif re.match(r"^[A-Za-z0-9+#.]+$", s):
            norm = s
            if s.lower() in {"api", "apis", "sql", "aws", "gcp", "ml", "ai", "ci", "cd", "html", "css", "nlp"}:
                norm = s.upper()
        else:
            norm = " ".join(w.capitalize() if w.isalpha() else w for w in s.split(" "))

        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def categorize_skills(*, skills: list[str]) -> tuple[list[str], list[str]]:
    """Split normalized skills into technical and soft skill groups."""
    technical: list[str] = []
    soft: list[str] = []
    for skill in skills:
        key = skill.lower()
        if key in _SOFT_SKILLS or any(soft_term in key for soft_term in _SOFT_SKILLS):
            soft.append(skill)
        else:
            technical.append(skill)
    return technical, soft


def split_primary_secondary(*, skills: list[str], skills_text: str) -> tuple[list[str], list[str]]:
    """Split normalized skills into primary and secondary groups."""
    if not skills:
        return [], []
    if skills_text.strip():
        n = min(8, max(3, len(skills) // 3))
        return skills[:n], skills[n:]
    return [], skills


def _clean_structured_line(line: str) -> str:
    """Clean a raw section line before structuring it."""
    line = _normalize_line(line)
    line = _BULLET_LINE_RE.sub("", line).strip()
    line = re.sub(r"\s+", " ", line)
    return line


def _chunk_section_lines(*, section_text: str) -> list[str]:
    """Convert a section block into clean non-empty lines."""
    return [line for line in (_clean_structured_line(line) for line in section_text.split("\n")) if line]


def _extract_job_title_and_company(line: str) -> tuple[str, str]:
    """Best-effort extraction of job title and company name from one experience line."""
    normalized = line.strip()
    if " at " in normalized.lower():
        parts = re.split(r"\bat\b", normalized, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(" |-,"), parts[1].strip(" |-,")
    for sep in (" | ", " - ", " — ", " @ "):
        if sep in normalized:
            left, right = normalized.split(sep, 1)
            if 1 <= len(left.split()) <= 6 and 1 <= len(right.split()) <= 8:
                return left.strip(" |-,"), right.strip(" |-,")
    return "", ""


def extract_experience_items(*, experience_text: str) -> list[dict[str, str]]:
    """Build lightweight structured experience entries from the experience section."""
    lines = _chunk_section_lines(section_text=experience_text)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 8 or line.lower() in seen:
            continue
        seen.add(line.lower())
        entry_type = "bullet" if len(line.split()) <= 18 else "summary"
        date_match = _DATE_HINT_RE.search(line)
        job_title, company_name = _extract_job_title_and_company(line)
        items.append(
            {
                "summary": line,
                "date_hint": date_match.group(0) if date_match else "",
                "entry_type": entry_type,
                "job_title": job_title,
                "company_name": company_name,
            }
        )
    return items[:20]


def extract_education_items(*, education_text: str) -> list[dict[str, str]]:
    """Build lightweight structured education entries from the education section."""
    lines = _chunk_section_lines(section_text=education_text)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 6 or line.lower() in seen:
            continue
        if not _DEGREE_HINT_RE.search(line) and len(line.split()) < 3:
            continue
        seen.add(line.lower())
        degree_hint = _DEGREE_HINT_RE.search(line)
        date_match = _DATE_HINT_RE.search(line)
        institution = ""
        for token in ("University", "College", "School", "Institute"):
            if token.lower() in line.lower():
                institution = line
                break
        items.append(
            {
                "summary": line,
                "category_hint": degree_hint.group(0) if degree_hint else "",
                "institution": institution,
                "date_hint": date_match.group(0) if date_match else "",
            }
        )
    return items[:15]


def extract_certification_items(*, certifications_text: str, education_text: str) -> list[dict[str, str]]:
    """Extract certification rows from certifications text or education fallback text."""
    source = certifications_text.strip() or education_text.strip()
    lines = _chunk_section_lines(section_text=source)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 5 or line.lower() in seen:
            continue
        if not _CERT_HINT_RE.search(line):
            continue
        seen.add(line.lower())
        date_match = _DATE_HINT_RE.search(line)
        issuer = ""
        for vendor in ("AWS", "Azure", "Google", "Oracle", "Coursera", "Udemy", "NPTEL", "Microsoft"):
            if vendor.lower() in line.lower():
                issuer = vendor
                break
        items.append({"summary": line, "issuer": issuer, "date_hint": date_match.group(0) if date_match else ""})
    return items[:15]


def extract_project_items(*, projects_text: str) -> list[dict[str, str]]:
    """Build lightweight structured project entries from the projects section."""
    lines = _chunk_section_lines(section_text=projects_text)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 8 or line.lower() in seen:
            continue
        if not _PROJECT_HINT_RE.search(line) and len(line.split()) < 3:
            continue
        seen.add(line.lower())
        items.append({"summary": line, "project_hint": "project" if _PROJECT_HINT_RE.search(line) else ""})
    return items[:20]


def build_parse_quality_meta(*, raw_text: str, sections: dict[str, str], skills: list[str], technical: list[str], soft: list[str]) -> dict[str, Any]:
    """Build lightweight quality metadata for the deterministic parser output."""
    sections_found = [name for name, value in sections.items() if value.strip()]
    missing_sections = [name for name in ("skills", "experience", "projects", "education", "certifications") if not sections.get(name, "").strip()]
    quality_flags: list[str] = []
    if not raw_text.strip():
        quality_flags.append("missing_raw_text")
    if not sections.get("skills", "").strip():
        quality_flags.append("missing_skills_section")
    if not sections.get("experience", "").strip():
        quality_flags.append("missing_experience_section")
    if not sections.get("projects", "").strip():
        quality_flags.append("missing_projects_section")
    if not sections.get("education", "").strip():
        quality_flags.append("missing_education_section")
    if len(skills) < 3:
        quality_flags.append("low_skill_coverage")
    if not technical:
        quality_flags.append("missing_technical_skills")
    if not soft:
        quality_flags.append("missing_soft_skills")
    return {
        "sections_found": sections_found,
        "missing_sections": missing_sections,
        "quality_flags": quality_flags,
        "is_low_confidence": bool("missing_raw_text" in quality_flags or "low_skill_coverage" in quality_flags or len(sections_found) < 2),
    }


def parse_resume_text(*, text: str) -> dict[str, Any]:
    """
    Parse resume text into validated deterministic structured JSON for storage.
    """
    raw_text = (text or "").strip()
    sections = extract_section_texts(text=raw_text)

    skill_items = extract_skill_items(skills_text=sections.get("skills", ""), full_text=raw_text)
    skills = normalize_skills(items=skill_items)
    technical, soft = categorize_skills(skills=skills)
    primary, secondary = split_primary_secondary(skills=skills, skills_text=sections.get("skills", ""))
    experience_items = extract_experience_items(experience_text=sections.get("experience", ""))
    education_items = extract_education_items(education_text=sections.get("education", ""))
    certification_items = extract_certification_items(
        certifications_text=sections.get("certifications", ""),
        education_text=sections.get("education", ""),
    )
    project_items = extract_project_items(projects_text=sections.get("projects", ""))
    quality_meta = build_parse_quality_meta(
        raw_text=raw_text,
        sections=sections,
        skills=skills,
        technical=technical,
        soft=soft,
    )

    warnings: list[str] = []
    if not raw_text:
        warnings.append("No extracted_text available to parse.")
    if not project_items and sections.get("projects", "").strip():
        warnings.append("Projects section detected but no structured project items were extracted.")
    if sections.get("certifications", "").strip() and not certification_items:
        warnings.append("Certifications section detected but no certification items were extracted.")

    payload: dict[str, Any] = {
        "version": 3,
        "sections": {
            "skills": {
                "text": sections.get("skills", ""),
                "items": skills,
                "primary": primary,
                "secondary": secondary,
                "technical": technical,
                "soft": soft,
            },
            "experience": {
                "text": sections.get("experience", ""),
                "items": experience_items,
            },
            "projects": {
                "text": sections.get("projects", ""),
                "items": project_items,
            },
            "education": {
                "text": sections.get("education", ""),
                "items": education_items,
            },
            "certifications": {
                "text": sections.get("certifications", ""),
                "items": certification_items,
            },
        },
        "raw": {
            "headings_found": quality_meta.get("sections_found", []),
            "warnings": warnings,
            "missing_sections": quality_meta.get("missing_sections", []),
            "quality_flags": quality_meta.get("quality_flags", []),
            "is_low_confidence": quality_meta.get("is_low_confidence", False),
        },
    }

    validated = ParsedResumeStructured.model_validate(payload)
    return validated.model_dump()
