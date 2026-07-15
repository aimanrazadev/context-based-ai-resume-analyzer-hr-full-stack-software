import json
from pathlib import Path

from fastapi import HTTPException

from ..database import SessionLocal
from ..models.candidate import Candidate
from ..models.job import Job
from ..services.ai_service import analyze_resume_for_job
from ..services.application_service import classify_required_skills_from_text
from ..services.application_serializer import job_required_skills_list
from ..services.embedding_service import embed_text
from ..services.matching_pipeline import evaluate_candidate_for_job
from ..services.progress_tracker import complete_task, fail_task, update_task
from ..services.resume_extractor import extract_and_clean_resume_text
from ..services.resume_parser import parse_resume_text
from ..services.similarity import cosine_similarity


def validated_extracted_text(extraction: dict) -> str:
    text_value = str(extraction.get("clean_text") or "").strip()
    if extraction.get("extraction_status") == "failed" or not text_value:
        raise HTTPException(
            status_code=422,
            detail=str(extraction.get("error_message") or "Could not read resume. Please upload a valid PDF or DOCX."),
        )
    return text_value


def extraction_metadata(extraction: dict) -> dict:
    return {
        key: value
        for key, value in extraction.items()
        if key not in {"raw_text", "clean_text"}
    }


async def run_scan_task(
    *,
    task_id: str,
    job_id: int,
    user_id: int,
    candidate_id: int,
    dest_path: str,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        candidate = db.query(Candidate).filter(Candidate.id == int(candidate_id)).first()
        if not job or not candidate:
            raise RuntimeError("Job or candidate not found")

        def prog(percent: int, message: str) -> None:
            update_task(task_id=task_id, percent=percent, message=message)

        prog(8, "Extracting text...")
        ext = Path(original_filename).suffix.lower()
        extraction = extract_and_clean_resume_text(file_path=str(dest_path), ext=ext)
        extracted = validated_extracted_text(extraction)

        prog(28, "Parsing resume...")
        structured = parse_resume_text(text=extracted)

        prog(74, "Computing similarity...")
        job_text = f"{job.job_title or ''}\n{job.job_description or ''}".strip()
        try:
            semantic_score = cosine_similarity(embed_text(extracted), embed_text(job_text))
        except Exception:
            semantic_score = 0.0

        prog(90, "Calculating final score...")
        required_skills = job_required_skills_list(job)
        live_snapshot = classify_required_skills_from_text(
            text=f"{extracted}\n{json.dumps(structured, ensure_ascii=False)}",
            required_skills=required_skills,
        )
        live_matched = live_snapshot.get("matched_skills") or []
        live_missing = live_snapshot.get("missing_skills") or []
        ai_analysis, ai_meta = await analyze_resume_for_job(
            structured_resume=structured,
            resume_text=extracted,
            job_title=job.job_title or "",
            job_description=job.job_description or "",
            required_skills=required_skills,
            matched_skills=live_matched,
            missing_skills=live_missing,
        )
        match_result = evaluate_candidate_for_job(
            job_title=job.job_title,
            job_description=job.job_description,
            job_required_skills=required_skills,
            resume_structured_json=json.dumps(structured, ensure_ascii=False),
            resume_ai_structured_json=None,
            semantic_score=float(semantic_score),
            ai_recommendation=str(ai_analysis.get("recommendation") or "Review Manually"),
        )
        breakdown = match_result.breakdown
        breakdown["matched_skills"] = live_matched
        breakdown["missing_skills"] = live_missing
        ai_analysis["matched_skills"] = live_matched
        ai_analysis["missing_skills"] = live_missing
        explanation = str(ai_analysis.get("reasoning") or ai_analysis.get("candidate_summary") or "")
        ai_error = None if ai_meta.get("status") == "success" else {
            "type": "ai_unavailable",
            "message": ai_meta.get("error_message") or "AI explanation could not be generated. The match score is still available.",
        }

        complete_task(
            task_id=task_id,
            result={
                "job_id": int(job.id),
                "ai_explanation": explanation or "",
                "ai_error": ai_error,
                "ai_analysis": ai_analysis,
                "semantic_score": round(float(semantic_score or 0.0) * 100.0, 2),
                "skills_score": float(match_result.skills_score or 0.0),
                "final_score": int(match_result.final_score or 0),
                "score_breakdown": breakdown,
                "_internal": {
                    "scan_file_path": str(dest_path),
                    "original_filename": original_filename,
                    "content_type": content_type,
                    "size_bytes": int(size_bytes or 0),
                    "extraction": extraction,
                    "structured": structured,
                    "ai_meta": ai_meta,
                },
            },
        )
    except Exception as e:
        fail_task(task_id=task_id, error_message=str(e))
    finally:
        db.close()
