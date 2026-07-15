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


def find_or_create_candidate(db: Session, *, user_id: int):
    from fastapi import HTTPException

    from ..models.candidate import Candidate
    from ..models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    candidate = db.query(Candidate).filter(Candidate.user_id == user.id).first()
    if not candidate and user.email:
        candidate = db.query(Candidate).filter(Candidate.email == user.email).first()
    if candidate:
        if candidate.user_id is None:
            candidate.user_id = user.id
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
        return candidate

    name = user.name or (user.email.split("@", 1)[0] if user.email else "Candidate")
    candidate = Candidate(name=name, email=user.email, user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def find_candidate_job_application(db: Session, *, candidate_id: int, job_id: int):
    from ..models.application import Application

    return (
        db.query(Application)
        .filter(Application.candidate_id == int(candidate_id), Application.job_id == int(job_id))
        .order_by(Application.created_at.asc())
        .first()
    )


def list_candidate_applications(db: Session, *, candidate_id: int):
    from ..models.application import Application

    return (
        db.query(Application)
        .filter(Application.candidate_id == int(candidate_id))
        .order_by(Application.created_at.desc())
        .all()
    )


def create_application_from_completed_scan(
    db: Session,
    *,
    job_id: int,
    user_id: int,
    task_id: str,
    upload_dir: str,
):
    from datetime import datetime, timezone
    from pathlib import Path

    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError

    from ..models.application import Application
    from ..models.job import Job
    from ..models.resume import Resume
    from ..modules.applications.status import normalize_application_status
    from ..modules.resumes.storage import copy_scan_to_application_storage, safe_unlink
    from ..services.progress_tracker import get_task
    from ..services.resume_scan_service import extraction_metadata

    job = db.query(Job).filter(Job.id == int(job_id)).first()
    if not job or (job.status or "active") != "active":
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = find_or_create_candidate(db, user_id=int(user_id))
    existing = find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
    if existing:
        return {"already_applied": True, "application": existing, "job": job}

    task = get_task(task_id=task_id)
    if (
        not task
        or int(task.get("user_id") or 0) != int(user_id)
        or int(task.get("job_id") or 0) != int(job_id)
        or task.get("status") != "done"
    ):
        raise HTTPException(status_code=404, detail="Completed scan not found. Please scan your resume again.")

    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    internal = result.get("_internal") if isinstance(result.get("_internal"), dict) else {}
    scan_file = Path(str(internal.get("scan_file_path") or ""))
    if not scan_file.exists():
        raise HTTPException(status_code=410, detail="Scanned resume expired. Please scan your resume again.")

    original_filename = Path(str(internal.get("original_filename") or scan_file.name)).name
    ext = Path(original_filename).suffix.lower() or scan_file.suffix.lower()
    if ext not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    dest, rel_path, stored_filename = copy_scan_to_application_storage(
        scan_file=scan_file,
        upload_dir=upload_dir,
        job_id=int(job_id),
        candidate_id=int(candidate.id),
        original_filename=original_filename,
    )

    extraction = internal.get("extraction") if isinstance(internal.get("extraction"), dict) else {}
    structured = internal.get("structured") if isinstance(internal.get("structured"), dict) else {}
    ai_meta = internal.get("ai_meta") if isinstance(internal.get("ai_meta"), dict) else {}
    ai_analysis = result.get("ai_analysis") if isinstance(result.get("ai_analysis"), dict) else {}
    breakdown = result.get("score_breakdown") if isinstance(result.get("score_breakdown"), dict) else {}

    try:
        resume = Resume(
            candidate_id=candidate.id,
            file_path=rel_path.as_posix(),
            stored_filename=stored_filename,
            original_filename=original_filename,
            content_type=internal.get("content_type"),
            size_bytes=int(internal.get("size_bytes") or 0),
            raw_extracted_text=extraction.get("raw_text") or "",
            extracted_text=extraction.get("clean_text") or "",
            extraction_status=str(extraction.get("extraction_status") or "success"),
            extraction_metadata_json=json.dumps(extraction_metadata(extraction), ensure_ascii=False),
            structured_json=json.dumps(structured, ensure_ascii=False),
            structured_version=int(structured.get("version") or 1),
            ai_structured_json=None,
            ai_structured_version=1,
            ai_model=str(ai_meta.get("model") or "") or None,
            ai_generated_at=datetime.now(timezone.utc) if ai_analysis else None,
            ai_warnings=json.dumps(ai_meta.get("warnings", []), ensure_ascii=False)
            if isinstance(ai_meta.get("warnings"), list)
            else None,
        )
        db.add(resume)
        db.flush()

        application = Application(job_id=job.id, candidate_id=candidate.id)
        application.resume_id = int(resume.id)
        application.ai_explanation = str(result.get("ai_explanation") or ai_analysis.get("reasoning") or "")
        application.status = normalize_application_status(None)
        application.semantic_score = float(result.get("semantic_score") or 0.0)
        application.skills_score = float(result.get("skills_score") or 0.0)
        application.experience_score = float(breakdown.get("experience_score") or 0.0)
        application.ai_score = float(breakdown.get("ai_score") or 0.0)
        application.final_score = int(result.get("final_score") or 0)
        application.matched_skills_json = json.dumps(ai_analysis.get("matched_skills") or breakdown.get("matched_skills") or [], ensure_ascii=False)
        application.missing_skills_json = json.dumps(ai_analysis.get("missing_skills") or breakdown.get("missing_skills") or [], ensure_ascii=False)
        application.ranking_explanation = application.ai_explanation
        application.score_breakdown_json = json.dumps(breakdown, ensure_ascii=False)
        application.score_updated_at = datetime.now(timezone.utc)
        db.add(application)
        db.flush()

        upsert_ai_resume_analysis(
            db,
            application_id=int(application.id),
            analysis=ai_analysis,
            metadata=ai_meta or {"status": "success"},
        )
        db.commit()
        db.refresh(application)
    except IntegrityError:
        db.rollback()
        safe_unlink(dest)
        existing = find_candidate_job_application(db, candidate_id=int(candidate.id), job_id=int(job_id))
        if existing:
            return {"already_applied": True, "application": existing, "job": job}
        raise HTTPException(status_code=409, detail="Application already exists") from None
    except Exception:
        db.rollback()
        safe_unlink(dest)
        raise

    safe_unlink(scan_file)

    return {
        "already_applied": False,
        "application": application,
        "job": job,
        "ai_analysis": ai_analysis,
        "breakdown": breakdown,
    }


def update_application_status_for_recruiter(db: Session, *, application_id: int, status: str, recruiter_id: int):
    from fastapi import HTTPException

    from ..models.application import Application
    from ..models.job import Job
    from ..modules.applications.status import ALLOWED_APPLICATION_STATUSES, normalize_application_status

    normalized = normalize_application_status(status)
    if normalized not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Invalid application status. Use not-reviewed, shortlisted, on-hold, or rejected.",
        )

    application = db.query(Application).filter(Application.id == int(application_id)).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == int(application.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if int(job.user_id or 0) != int(recruiter_id):
        raise HTTPException(status_code=403, detail="You can only update applications for your own jobs")

    application.status = normalized
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def delete_application_for_user(db: Session, *, application_id: int, user: dict, upload_dir: str) -> int:
    from pathlib import Path

    from fastapi import HTTPException

    from ..models.application import Application
    from ..models.embedding import Embedding
    from ..models.job import Job
    from ..models.resume import Resume

    application = db.query(Application).filter(Application.id == int(application_id)).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == int(application.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_role = user.get("role")
    user_id = int(user.get("sub"))
    if user_role == "recruiter":
        if job.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only delete applications for your own jobs")
    elif user_role == "candidate":
        candidate = find_or_create_candidate(db, user_id=user_id)
        if application.candidate_id != candidate.id:
            raise HTTPException(status_code=403, detail="You can only withdraw your own applications")
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")

    resume_id = application.resume_id
    job_id = int(application.job_id)
    try:
        delete_ai_resume_analysis(db, application_id=int(application.id))
        db.delete(application)
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        if resume_id:
            db.query(Embedding).filter(Embedding.entity_type == "resume", Embedding.entity_id == int(resume_id)).delete(synchronize_session=False)
            resume = db.query(Resume).filter(Resume.id == int(resume_id)).first()
            if resume:
                try:
                    path = Path(upload_dir) / (resume.file_path or "")
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass
                db.delete(resume)
                db.commit()
    except Exception:
        db.rollback()

    return job_id
