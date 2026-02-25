import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..models.candidate import Candidate
from ..models.resume import Resume
from ..models.user import User
from ..services.resume_analysis import extract_and_clean_resume_text
from ..services.resume_parsing import parse_resume_text
from ..services.ai_resume_structuring import ai_structure_resume
from ..services.embeddings import get_or_create_embedding
from ..utils.roles import candidate_only
from ..utils.validation import sanitize_filename, validate_integer_field
from ..utils.error_handlers import (
    get_error_message,
    handle_file_upload_error,
    handle_ai_service_error,
    handle_database_error
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["Resumes"])

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",  # sometimes used incorrectly for docx by browsers
    "application/octet-stream",  # allow when extension is trusted
}
MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5MB


def _find_or_create_candidate(db: Session, *, user_id: int) -> Candidate:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    candidate = db.query(Candidate).filter(Candidate.email == user.email).first()
    if candidate:
        return candidate

    # Backfill: if a candidate user exists without a Candidate row (older DB), create it.
    name = user.name or (user.email.split("@", 1)[0] if user.email else "Candidate")
    candidate = Candidate(name=name, email=user.email)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def _public_resume(r: Resume) -> dict:
    return {
        "id": r.id,
        "candidate_id": r.candidate_id,
        "original_filename": r.original_filename,
        "stored_filename": r.stored_filename,
        "content_type": r.content_type,
        "size_bytes": r.size_bytes,
        "file_path": r.file_path,
        "has_structured": bool(getattr(r, "structured_json", None)),
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
    }


class ResumeListResponse(BaseModel):
    success: bool
    resumes: list[dict]


@router.get("/mine", response_model=ResumeListResponse)
def list_my_resumes(
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    rows = (
        db.query(Resume)
        .filter(Resume.candidate_id == candidate.id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    return {"success": True, "resumes": [_public_resume(r) for r in rows]}


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    # Validate file presence
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail=get_error_message("invalid_file_type")
        )

    # Sanitize and validate filename
    try:
        original_filename = sanitize_filename(Path(file.filename).name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Filename sanitization error: {e}")
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Validate file extension
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=get_error_message("invalid_file_type")
        )

    # Validate content type
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=get_error_message("invalid_file_type")
        )

    # Get or create candidate
    try:
        candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    except Exception as e:
        logger.error(f"Error finding/creating candidate: {e}")
        raise handle_database_error(e, "finding candidate")

    # Prepare storage paths
    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(UPLOAD_DIR) / "resumes" / str(candidate.id)
    
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create upload directory: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to prepare storage"
        )

    dest = base_dir / stored_filename
    rel_path = Path("resumes") / str(candidate.id) / stored_filename

    # Save file with size validation
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESUME_BYTES:
                    # Clean up partial file
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=413,
                        detail=get_error_message("file_too_large")
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Clean up partial file
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        logger.error(f"File save error: {e}")
        raise handle_file_upload_error(e, original_filename)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    # Extract + clean (Module 6)
    try:
        extraction = extract_and_clean_resume_text(file_path=dest.as_posix(), ext=ext)
        extracted_text = extraction.get("clean_text") or ""
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            logger.warning(f"Extracted text too short for {original_filename}")
            # Continue anyway, don't fail
    except Exception as e:
        logger.error(f"Resume extraction error: {e}")
        # Don't fail completely - use empty text
        extracted_text = ""

    # Parse resume structure
    try:
        structured = parse_resume_text(text=extracted_text)
    except Exception as e:
        logger.error(f"Resume parsing error: {e}")
        structured = {"version": 1}  # Fallback to minimal structure

    # AI structuring with fallback
    ai_structured = None
    ai_structured_meta = {}
    try:
        ai_structured, ai_structured_meta = await ai_structure_resume(resume_text=extracted_text)
    except Exception as e:
        logger.error(f"AI structuring error: {e}")
        error_info = handle_ai_service_error(e, "resume structuring")
        # Continue without AI structuring
        ai_structured_meta = {"error": error_info.get("message")}

    # Save to database
    resume = Resume(
        candidate_id=candidate.id,
        file_path=rel_path.as_posix(),
        stored_filename=stored_filename,
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=size,
        extracted_text=extracted_text,
        structured_json=json.dumps(structured, ensure_ascii=False),
        structured_version=int(structured.get("version") or 1),
        ai_structured_json=json.dumps(ai_structured, ensure_ascii=False) if ai_structured else None,
        ai_structured_version=int((ai_structured or {}).get("version") or 1) if ai_structured else 1,
        ai_model=(ai_structured_meta.get("model") if isinstance(ai_structured_meta, dict) else None),
        ai_generated_at=datetime.now(timezone.utc) if ai_structured else None,
        ai_warnings=json.dumps(ai_structured_meta.get("warnings", []), ensure_ascii=False)
        if isinstance(ai_structured_meta, dict) and ai_structured_meta.get("warnings")
        else None,
    )
    
    try:
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except Exception as e:
        db.rollback()
        # Clean up uploaded file
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        logger.error(f"Database error saving resume: {e}")
        raise handle_database_error(e, "saving resume")

    # Module 9: store resume embedding (best-effort)
    try:
        if extracted_text:
            get_or_create_embedding(db, entity_type="resume", entity_id=resume.id, text=extracted_text)
    except Exception as e:
        logger.warning(f"Failed to create embedding for resume {resume.id}: {e}")
        # Don't fail upload if embedding fails

    return {"success": True, "resume": _public_resume(resume)}


@router.get("/{resume_id}/download")
def download_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    # Validate resume_id
    try:
        resume_id = validate_integer_field(resume_id, "resume_id", min_value=1)
    except HTTPException:
        raise
    
    try:
        candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
    except Exception as e:
        logger.error(f"Database error fetching resume: {e}")
        raise handle_database_error(e, "fetching resume")
    
    if not resume or resume.candidate_id != candidate.id:
        raise HTTPException(
            status_code=404,
            detail=get_error_message("not_found")
        )

    abs_path = Path(UPLOAD_DIR) / Path(resume.file_path)
    if not abs_path.exists():
        logger.error(f"Resume file missing on server: {abs_path}")
        raise HTTPException(
            status_code=404,
            detail="File no longer available on server"
        )

    try:
        # FileResponse handles streaming efficiently
        return FileResponse(
            abs_path,
            media_type=resume.content_type or "application/octet-stream",
            filename=resume.original_filename,
        )
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to download file"
        )


@router.get("/{resume_id}/structured")
def get_structured_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user=Depends(candidate_only),
):
    candidate = _find_or_create_candidate(db, user_id=int(user.get("sub")))
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume or resume.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Resume not found")

    if not getattr(resume, "structured_json", None):
        return {"success": True, "structured": None, "version": getattr(resume, "structured_version", 1) or 1}

    try:
        structured = json.loads(resume.structured_json)
    except Exception:
        structured = None

    return {
        "success": True,
        "structured": structured,
        "version": getattr(resume, "structured_version", 1) or 1,
    }

