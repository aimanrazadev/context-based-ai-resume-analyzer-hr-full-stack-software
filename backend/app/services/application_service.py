import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ..modules.matching.skills import (
    classify_required_skills,
    contains_skill,
    normalize_required_skills,
)
from ..models.ai_resume_analysis import AIResumeAnalysis


_EVALUATIVE_SUMMARY_PATTERNS = (
    "demonstrates",
    "strong proficiency",
    "lacks",
    "missing",
    "is missing",
    "the candidate matches",
    "matches ",
    "strong fit",
    "good fit",
    "weak fit",
    "suitable",
    "recommend",
    "candidate is",
    "but lacks",
)


def is_evaluative_candidate_summary(text: str | None) -> bool:
    summary = str(text or "").strip().lower()
    return any(pattern in summary for pattern in _EVALUATIVE_SUMMARY_PATTERNS)


def _load_json(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _first_items(value: Any, limit: int = 3) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(re.sub(r"\s+", " ", text))
        if len(result) >= limit:
            break
    return result


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _resume_text_blob(resume: Any | None) -> str:
    if not resume:
        return ""
    pieces = [
        getattr(resume, "extracted_text", None),
        getattr(resume, "raw_extracted_text", None),
        getattr(resume, "structured_json", None),
        getattr(resume, "ai_structured_json", None),
    ]
    return "\n".join(str(piece or "") for piece in pieces if piece)


def _section_between(text: str, start: str, stops: tuple[str, ...]) -> str:
    pattern = re.compile(rf"{re.escape(start)}\s*(.*?)(?:{'|'.join(re.escape(stop) for stop in stops)}|$)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text or "")
    return match.group(1).strip() if match else ""


def _raw_project_names(text: str, limit: int = 2) -> list[str]:
    names: list[str] = []
    for line in (text or "").splitlines():
        clean = _clean_text(line)
        if "|" not in clean:
            continue
        left = clean.split("|", 1)[0].strip(" -–")
        if left and "github" not in left.lower() and len(left) <= 90:
            names.append(left)
        if len(names) >= limit:
            break
    return names


def _raw_education(text: str) -> str:
    block = _section_between(text, "Education", ("Projects", "Experience", "Technical Skills", "Skills"))
    lines = [_clean_text(line) for line in block.splitlines() if _clean_text(line)]
    return " ".join(lines[:4])


def _raw_projects_sentence(text: str) -> str:
    names = _raw_project_names(text, 2)
    if names:
        return f"Major projects include {', '.join(names)}."
    return ""


def _raw_soft_skill_note(text: str) -> str:
    lower = (text or "").lower()
    signals = []
    if "collaborat" in lower:
        signals.append("collaboration")
    if "communicat" in lower:
        signals.append("communication")
    if "problem" in lower or "debug" in lower:
        signals.append("problem solving")
    if signals:
        return f"Soft-skill signals visible in the resume include {', '.join(dict.fromkeys(signals))}."
    return "Soft skills should be verified through the non-negotiables and interview process."


def classify_required_skills_from_resume(resume: Any | None, required_skills: list[str] | None) -> dict[str, list[str]]:
    text = _resume_text_blob(resume)
    return classify_required_skills_from_text(text=text, required_skills=required_skills)


def classify_required_skills_from_text(*, text: str, required_skills: list[str] | None) -> dict[str, list[str]]:
    return classify_required_skills(text=text, required_skills=required_skills)


def analysis_conflicts_with_skill_snapshot(analysis: dict[str, Any], matched_skills: list[str]) -> bool:
    text_parts: list[str] = []
    for key in ("weaknesses", "weakness_reasoning"):
        value = analysis.get(key)
        if isinstance(value, list):
            text_parts.extend(str(item or "") for item in value)
        else:
            text_parts.append(str(value or ""))
    text = " ".join(text_parts)
    return any(contains_skill(text, skill) for skill in matched_skills or [])


def factual_candidate_summary_from_resume(resume: Any | None) -> str:
    if not resume:
        return ""

    payload = _load_json(getattr(resume, "ai_structured_json", None)) or _load_json(getattr(resume, "structured_json", None))
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}

    skills = sections.get("skills") if isinstance(sections.get("skills"), dict) else {}
    projects = sections.get("projects") if isinstance(sections.get("projects"), dict) else {}
    education = sections.get("education") if isinstance(sections.get("education"), dict) else {}
    experience = sections.get("experience") if isinstance(sections.get("experience"), dict) else {}

    skill_items = _first_items(skills.get("primary") or skills.get("items"), 6)
    project_items = _first_items(projects.get("items"), 2)
    education_items = _first_items(education.get("items"), 1)
    experience_items = _first_items(experience.get("items") or experience.get("bullets"), 1)
    resume_text = str(getattr(resume, "extracted_text", None) or getattr(resume, "raw_extracted_text", None) or "")
    if not project_items:
        project_items = _raw_project_names(resume_text, 2)
    if not education_items:
        raw_education = _raw_education(resume_text)
        education_items = [raw_education] if raw_education else []

    parts: list[str] = []
    if project_items:
        parts.append(f"Major projects include {'; '.join(project_items)}.")
    if education_items:
        parts.append(f"Education: {education_items[0]}.")
    if skill_items:
        parts.append(f"Core technical stack includes {', '.join(skill_items)}.")
    if experience_items:
        parts.append(f"Experience: {experience_items[0]}.")
    parts.append(_raw_soft_skill_note(resume_text))

    if parts:
        return " ".join(parts[:4])

    extracted = str(getattr(resume, "extracted_text", None) or "").strip()
    if extracted:
        return re.sub(r"\s+", " ", extracted).split("\n")[0][:350]
    return ""


def deterministic_insights_from_resume(
    resume: Any | None,
    *,
    matched_skills: list[str] | None,
    missing_skills: list[str] | None,
) -> dict[str, Any]:
    resume_text = str(getattr(resume, "extracted_text", None) or getattr(resume, "raw_extracted_text", None) or "")
    matched = [_clean_text(skill) for skill in matched_skills or [] if _clean_text(skill)]
    missing = [_clean_text(skill) for skill in missing_skills or [] if _clean_text(skill)]

    strengths: list[str] = []
    if matched:
        strengths.append(f"Matches required skills: {', '.join(matched[:8])}.")
    project_sentence = _raw_projects_sentence(resume_text)
    if project_sentence:
        strengths.append(project_sentence)
    education = _raw_education(resume_text)
    if education:
        strengths.append(f"Education evidence: {education}.")
    soft_note = _raw_soft_skill_note(resume_text)
    if soft_note:
        strengths.append(soft_note)

    weaknesses: list[str] = []
    if missing:
        weaknesses.append(f"Missing or not explicit in resume: {', '.join(missing[:6])}.")
    else:
        weaknesses.append("No major required-skill gaps detected from the uploaded resume.")

    reasoning_parts = []
    if matched:
        reasoning_parts.append(f"The resume explicitly supports {len(matched)} required skill(s).")
    if missing:
        reasoning_parts.append(f"{len(missing)} required skill(s) need verification.")
    if project_sentence:
        reasoning_parts.append(project_sentence)

    return {
        "candidate_summary": factual_candidate_summary_from_resume(resume),
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "strength_reasoning": " ".join(strengths),
        "weakness_reasoning": " ".join(weaknesses),
        "reasoning": " ".join(reasoning_parts) or "Deterministic resume evidence was used because AI insight text was unavailable or incomplete.",
    }


def upsert_ai_resume_analysis(
    db: Session,
    *,
    application_id: int,
    analysis: dict[str, Any],
    metadata: dict[str, Any],
) -> AIResumeAnalysis:
    """Persist the single canonical AI explanation for an application."""
    row = db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).first()
    if row is None:
        row = AIResumeAnalysis(application_id=application_id)
    row.candidate_summary = str(analysis.get("candidate_summary") or "")
    row.strengths_json = json.dumps(analysis.get("strengths") or [], ensure_ascii=False)
    row.weaknesses_json = json.dumps(analysis.get("weaknesses") or [], ensure_ascii=False)
    row.strength_reasoning = str(analysis.get("strength_reasoning") or "")
    row.weakness_reasoning = str(analysis.get("weakness_reasoning") or "")
    row.matched_skills_json = json.dumps(analysis.get("matched_skills") or [], ensure_ascii=False)
    row.missing_skills_json = json.dumps(analysis.get("missing_skills") or [], ensure_ascii=False)
    row.recommendation = str(analysis.get("recommendation") or "Review Manually")
    row.reasoning = str(analysis.get("reasoning") or "")
    row.provider = "gemini"
    row.model = str(metadata.get("model") or "") or None
    row.status = str(metadata.get("status") or "success")
    row.error_message = str(metadata.get("error_message") or "") or None
    db.add(row)
    db.flush()
    return row


def ai_analysis_payload(db: Session, *, application_id: int) -> dict[str, Any] | None:
    row = db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).first()
    if row is None:
        return None

    def load_list(raw: str | None) -> list[str]:
        try:
            value = json.loads(raw or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    return {
        "candidate_summary": row.candidate_summary,
        "strengths": load_list(row.strengths_json),
        "weaknesses": load_list(row.weaknesses_json),
        "strength_reasoning": row.strength_reasoning or "",
        "weakness_reasoning": row.weakness_reasoning or "",
        "matched_skills": load_list(row.matched_skills_json),
        "missing_skills": load_list(row.missing_skills_json),
        "recommendation": row.recommendation,
        "reasoning": row.reasoning,
        "status": row.status,
    }


def delete_ai_resume_analysis(db: Session, *, application_id: int) -> None:
    db.query(AIResumeAnalysis).filter(AIResumeAnalysis.application_id == application_id).delete(synchronize_session=False)


def backfill_missing_application_scores(db: Session) -> int:
    """Upgrade legacy applications once to the canonical stored scoring formula."""
    from datetime import datetime, timezone

    from ..models.application import Application
    from ..models.resume import Resume
    from .matching_pipeline import evaluate_candidate_for_job

    rows = db.query(Application).filter(Application.experience_score.is_(None)).all()
    updated = 0
    recommendation_map = {"strong_yes": "Strong Fit", "yes": "Good Fit", "maybe": "Average Fit", "no": "Weak Fit"}
    for application in rows:
        job = application.job
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first() if application.resume_id else None
        if not job or not resume:
            continue
        ai_payload: dict[str, Any] = {}
        try:
            raw_ai = json.loads(resume.ai_structured_json or "{}")
            ai_payload = raw_ai.get("analysis") if isinstance(raw_ai.get("analysis"), dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            ai_payload = {}
        raw_recommendation = str(ai_payload.get("hiring_recommendation") or "").strip()
        recommendation = recommendation_map.get(raw_recommendation, raw_recommendation.replace("_", " ").title())
        if recommendation not in {"Strong Fit", "Good Fit", "Average Fit", "Review Manually", "Weak Fit"}:
            recommendation = "Review Manually"
        semantic_normalized = float(application.semantic_score or 0.0)
        if semantic_normalized > 1.0:
            semantic_normalized /= 100.0
        match_result = evaluate_candidate_for_job(
            job_title=job.job_title,
            job_description=job.job_description,
            job_required_skills=normalize_required_skills(job.required_skills),
            resume_structured_json=resume.structured_json,
            resume_ai_structured_json=resume.ai_structured_json,
            semantic_score=semantic_normalized,
            ai_recommendation=recommendation,
        )
        skills_score = match_result.skills_score
        final_score = match_result.final_score
        breakdown = match_result.breakdown
        application.semantic_score = round(semantic_normalized * 100.0, 2)
        application.skills_score = skills_score
        application.experience_score = float(breakdown.get("experience_score") or 0.0)
        application.ai_score = float(breakdown.get("ai_score") or 0.0)
        application.final_score = final_score
        application.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
        application.matched_skills_json = json.dumps(breakdown.get("matched_skills") or [], ensure_ascii=False)
        application.missing_skills_json = json.dumps(breakdown.get("missing_skills") or [], ensure_ascii=False)
        application.ranking_explanation = str(ai_payload.get("reasoning") or application.ai_explanation or "")
        application.score_updated_at = datetime.now(timezone.utc)
        analysis = {
            "candidate_summary": ai_payload.get("candidate_summary") or factual_candidate_summary_from_resume(resume),
            "strengths": ai_payload.get("strengths") or [],
            "weaknesses": ai_payload.get("weaknesses") or [],
            "strength_reasoning": ai_payload.get("strength_reasoning") or "",
            "weakness_reasoning": ai_payload.get("weakness_reasoning") or "",
            "matched_skills": breakdown.get("matched_skills") or [],
            "missing_skills": breakdown.get("missing_skills") or [],
            "recommendation": recommendation,
            "reasoning": application.ranking_explanation,
        }
        upsert_ai_resume_analysis(db, application_id=int(application.id), analysis=analysis, metadata={"status": "migrated", "model": resume.ai_model})
        updated += 1
    if updated:
        db.commit()
    return updated
