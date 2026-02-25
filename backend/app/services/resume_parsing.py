import json
import os
import re
from typing import Any


_HEADING_ALIASES: dict[str, list[str]] = {
    "skills": [
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "skills & tools",
        "tools",
        "technologies",
        "tech stack",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "internships",
        "projects",
        "project experience",
    ],
    "education": [
        "education",
        "academic",
        "academic background",
        "education & certifications",
        "certifications",
        "certification",
    ],
}

_LINE_CLEAN_RE = re.compile(r"[\t ]{2,}")
_BULLET_LINE_RE = re.compile(r"^\s*[-•\u2022]\s+")
_SKILL_SPLIT_RE = re.compile(r"[,/|•\u2022;\n]+")
_WORD_SKILL_RE = re.compile(r"[A-Za-z0-9+#.]{2,}")


def _normalize_line(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _LINE_CLEAN_RE.sub(" ", s).strip()
    return s


def _canonical_heading(line: str) -> str | None:
    """
    Returns canonical section key if the line looks like a heading.
    """
    raw = _normalize_line(line)
    if not raw:
        return None

    # Drop trailing punctuation like ":" or "-"
    key = raw.strip().strip(":").strip("-").strip().lower()
    key = re.sub(r"[^a-z0-9 &]+", "", key).strip()
    if not key:
        return None

    for canonical, aliases in _HEADING_ALIASES.items():
        if key == canonical:
            return canonical
        if key in aliases:
            return canonical
    return None


def detect_sections(*, text: str) -> dict[str, dict[str, Any]]:
    """
    Find section boundaries by scanning headings line-by-line.
    Returns mapping canonical section -> {start, end, heading_line}.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        canon = _canonical_heading(line)
        if canon:
            hits.append((i, canon, _normalize_line(line)))

    # De-dup consecutive duplicates (e.g. repeated headings)
    dedup: list[tuple[int, str, str]] = []
    for i, canon, hline in hits:
        if dedup and dedup[-1][1] == canon and (i - dedup[-1][0]) <= 2:
            continue
        dedup.append((i, canon, hline))

    # Compute spans
    spans: dict[str, dict[str, Any]] = {}
    for idx, (line_idx, canon, hline) in enumerate(dedup):
        end = len(lines)
        if idx + 1 < len(dedup):
            end = dedup[idx + 1][0]
        spans[canon] = {"start": line_idx + 1, "end": end, "heading_line": hline}

    return spans


def _slice_text(lines: list[str], start: int, end: int) -> str:
    chunk = "\n".join(lines[start:end]).strip()
    return chunk


def extract_section_texts(*, text: str) -> dict[str, str]:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    spans = detect_sections(text=text)
    out: dict[str, str] = {}
    for sec in ("skills", "experience", "education"):
        meta = spans.get(sec)
        out[sec] = _slice_text(lines, meta["start"], meta["end"]) if meta else ""
    return out


def extract_skill_items(*, skills_text: str, full_text: str) -> list[str]:
    """
    Extract skill tokens primarily from skills section; fallback to full text.
    Keeps multi-token items only when present as known patterns (e.g. 'machine learning' often becomes two tokens).
    """
    base = skills_text.strip() or full_text.strip()
    if not base:
        return []

    # Prefer bullet lines and comma-separated lists
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
        # If it's a short phrase (<= 3 words) keep as phrase, else tokenize
        words = _WORD_SKILL_RE.findall(p)
        if not words:
            continue
        if len(words) <= 3 and len(p) <= 40:
            tokens.append(" ".join(words))
        else:
            tokens.extend(words)
    return tokens


def normalize_skills(*, items: list[str]) -> list[str]:
    """
    Normalize + deduplicate skills while preserving common casing for acronyms.
    """
    out: list[str] = []
    seen: set[str] = set()

    for raw in items:
        s = _normalize_line(raw)
        s = s.strip(" -•\u2022").strip()
        if not s:
            continue
        # Normalize common noise
        s = re.sub(r"[^A-Za-z0-9+#. ]+", " ", s).strip()
        s = _LINE_CLEAN_RE.sub(" ", s)
        if len(s) < 2 or len(s) > 40:
            continue

        # Title-case words unless looks like acronym / version / camel-case token
        if s.isupper():
            norm = s
        elif re.match(r"^[A-Za-z]{1,6}\d+(\.\d+)?$", s):
            norm = s
        elif re.match(r"^[A-Za-z0-9+#.]+$", s):
            # Single token: preserve as-is but uppercase common acronyms
            norm = s
            if s.lower() in {"api", "apis", "sql", "aws", "gcp", "ml", "ai", "ci", "cd"}:
                norm = s.upper()
        else:
            norm = " ".join(w.capitalize() if w.isalpha() else w for w in s.split(" "))

        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)

    return out


def split_primary_secondary(*, skills: list[str], skills_text: str) -> tuple[list[str], list[str]]:
    """
    Simple heuristic:
    - if skills section exists: first N become primary, rest secondary
    - else: all are secondary (we don't know emphasis)
    """
    if not skills:
        return [], []
    if skills_text.strip():
        n = min(8, max(3, len(skills) // 3))
        return skills[:n], skills[n:]
    return [], skills


def _maybe_refine_with_llm(*, payload: dict) -> tuple[dict, list[str]]:
    """
    Optional LLM refinement hook (best-effort).\n+\n+    This will only run when AI_API_KEY is set AND LLM_ENDPOINT + LLM_MODEL are provided.\n+    If not configured, returns payload unchanged.\n+    """
    warnings: list[str] = []
    if not os.getenv("AI_API_KEY"):
        return payload, warnings

    endpoint = os.getenv("LLM_ENDPOINT")
    model = os.getenv("LLM_MODEL")
    if not endpoint or not model:
        warnings.append("LLM refinement skipped: set LLM_ENDPOINT and LLM_MODEL to enable.")
        return payload, warnings

    # Best-effort, no hard failure: we don't want parsing to break uploads
    try:
        import httpx

        prompt = (
            "You are a resume parser. Given extracted skills, return JSON with two arrays: "
            "primary and secondary skills. Keep items short and deduplicated.\n\n"
            f"Skills: {payload.get('sections', {}).get('skills', {}).get('items', [])}"
        )
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {os.getenv('AI_API_KEY')}"}
        with httpx.Client(timeout=20.0) as client:
            r = client.post(endpoint, json=body, headers=headers)
        if r.status_code >= 400:
            warnings.append(f"LLM refinement failed: HTTP {r.status_code}.")
            return payload, warnings

        data = r.json()
        # Support OpenAI-style response
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = json.loads(content)
        primary = parsed.get("primary") or []
        secondary = parsed.get("secondary") or []
        payload["sections"]["skills"]["primary"] = primary
        payload["sections"]["skills"]["secondary"] = secondary
        payload["sections"]["skills"]["llm_refined"] = True
        return payload, warnings
    except Exception:
        warnings.append("LLM refinement failed due to an unexpected error.")
        return payload, warnings


def parse_resume_text(*, text: str) -> dict[str, Any]:
    """
    Parse resume text into structured sections and normalized skills.
    Returns a JSON-serializable dict suitable for storing in resumes.structured_json.
    """
    raw_text = (text or "").strip()
    sections = extract_section_texts(text=raw_text)

    skill_items = extract_skill_items(skills_text=sections.get("skills", ""), full_text=raw_text)
    skills = normalize_skills(items=skill_items)
    primary, secondary = split_primary_secondary(skills=skills, skills_text=sections.get("skills", ""))

    payload: dict[str, Any] = {
        "version": 1,
        "sections": {
            "skills": {
                "text": sections.get("skills", ""),
                "items": skills,
                "primary": primary,
                "secondary": secondary,
                "llm_refined": False,
            },
            "experience": {"text": sections.get("experience", ""), "items": []},
            "education": {"text": sections.get("education", ""), "items": []},
        },
        "raw": {
            "headings_found": [k for k, v in detect_sections(text=raw_text).items() if v],
            "warnings": [],
        },
    }

    payload, llm_warnings = _maybe_refine_with_llm(payload=payload)
    if llm_warnings:
        payload["raw"]["warnings"].extend(llm_warnings)

    if not raw_text:
        payload["raw"]["warnings"].append("No extracted_text available to parse.")

    return payload

