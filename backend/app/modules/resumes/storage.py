from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import HTTPException, UploadFile


def validate_resume_upload(
    file: UploadFile | None,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
) -> tuple[str, str]:
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    original_filename = Path(file.filename).name
    ext = Path(original_filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.content_type and file.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    return original_filename, ext


def build_resume_storage_path(
    *,
    upload_dir: str,
    bucket: str,
    job_id: int,
    candidate_id: int,
    ext: str,
) -> tuple[Path, str]:
    stored_filename = f"{uuid4().hex}{ext}"
    base_dir = Path(upload_dir) / bucket / str(job_id) / str(candidate_id)
    return base_dir / stored_filename, stored_filename


def safe_unlink(path: Path | str | None) -> None:
    if not path:
        return
    try:
        target = Path(path)
        if target.exists():
            target.unlink()
    except Exception:
        pass


async def save_upload_file(file: UploadFile, dest: Path, *, max_bytes: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="File too large (max 5MB)")
                out.write(chunk)
    except HTTPException:
        safe_unlink(dest)
        raise
    except Exception:
        safe_unlink(dest)
        raise HTTPException(status_code=500, detail="Failed to store file") from None
    finally:
        try:
            await file.close()
        except Exception:
            pass
    return size


def copy_scan_to_application_storage(
    *,
    scan_file: Path,
    upload_dir: str,
    job_id: int,
    candidate_id: int,
    original_filename: str,
) -> tuple[Path, Path, str]:
    ext = Path(original_filename).suffix.lower() or scan_file.suffix.lower()
    dest, stored_filename = build_resume_storage_path(
        upload_dir=upload_dir,
        bucket="applications",
        job_id=job_id,
        candidate_id=candidate_id,
        ext=ext,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(scan_file, dest)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save scanned resume") from None
    rel_path = Path("applications") / str(job_id) / str(candidate_id) / stored_filename
    return dest, rel_path, stored_filename
