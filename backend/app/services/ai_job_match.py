import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import (
    AI_LOG_PAYLOADS,
    AI_MAX_RETRIES,
    AI_TIMEOUT_S,
    GEMINI_API_KEY,
    GEMINI_API_VERSION,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
)
from ..schemas.ai_match import AIMatchOutput, AISectionedMatch
from .ai_client import AIClientError, AIClientHTTPError, gemini_generate_content
from .ai_common import extract_first_json_object
from .ai_prompts import job_match_sectioned_user_prompt, job_match_system_prompt
from .ai_match_cache import get_cached_match, cache_match_result


logger = logging.getLogger(__name__)


def _sanitize_list(items: list[str], n: int) -> list[str]:
    """
    Trim and truncate a list of model-generated bullet strings.

    Args:
        items: Source list from model output.
        n: Maximum number of items to keep.

    Returns:
        A cleaned list of non-empty strings.

    Side Effects:
        None.

    Error Handling:
        Treats falsy inputs as empty lists and skips invalid values.
    """
    return [str(x).strip() for x in (items or []) if str(x).strip()][:n]


def _sanitize_text(s: str, max_len: int = 1200) -> str:
    """
    Normalize and cap a free-form model-generated string.

    Args:
        s: Raw model text.
        max_len: Maximum number of characters to keep.

    Returns:
        A cleaned and length-limited string.
    """
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _sanitize_summary(s: str, max_len: int = 220) -> str:
    """
    Compress a summary to roughly two recruiter-friendly sentences.

    Args:
        s: Raw summary text from the model.
        max_len: Maximum number of characters to keep.

    Returns:
        A short, UI-friendly summary string.

    Side Effects:
        None.

    Error Handling:
        Falls back to a truncated raw string when sentence splitting is weak.
    """
    s = (s or "").strip()
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", s) if p.strip()]
    s2 = " ".join(parts[:2]) if parts else s
    if len(s2) > max_len:
        return s2[:max_len] + "..."
    return s2


async def ai_match_resume_to_job(
    *,
    job_title: str | None,
    job_description: str | None,
    resume_text: str,
    db: Session | None = None,
    job_id: int | None = None,
    resume_id: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Generate an AI-assisted job match analysis for a resume.

    Args:
        job_title: Job title text, if available.
        job_description: Job description text, if available.
        resume_text: Resume text to compare against the job.
        db: Optional database session for cache lookup and storage.
        job_id: Optional job identifier for cache lookup.
        resume_id: Optional resume identifier for cache lookup.

    Returns:
        A tuple containing:
        - AI match output or None
        - metadata describing enablement, cache usage, warnings, and timing

    Side Effects:
        May perform a cache lookup, an outbound AI request, and cache the
        successful result.

    Error Handling:
        Returns `(None, meta)` on parse, validation, HTTP, network, or
        unexpected failures rather than raising into the calling flow.
    """
    meta: dict[str, Any] = {
        "enabled": bool(GEMINI_API_KEY),
        "warnings": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": GEMINI_MODEL,
        "validated_schema": False,
    }
    if not GEMINI_API_KEY:
        meta["warnings"].append("AI disabled: GEMINI_API_KEY not configured.")
        return None, meta

    if db and job_id and resume_id:
        cached = get_cached_match(db, job_id=job_id, resume_id=resume_id)
        if cached:
            meta["from_cache"] = True
            meta["cached_hit"] = True
            return cached, meta

    if db and not (job_id and resume_id):
        cached = get_cached_match(
            db,
            job_text=f"{job_title or ''}\n{job_description or ''}",
            resume_text=resume_text,
        )
        if cached:
            meta["from_cache"] = True
            meta["cached_by_content"] = True
            return cached, meta

    user_prompt = job_match_sectioned_user_prompt(
        job_title=job_title,
        job_description=job_description,
        resume_text=resume_text or "",
    )
    system_prompt = job_match_system_prompt()

    try:
        raw_text, call_meta = await gemini_generate_content(
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
            api_version=GEMINI_API_VERSION,
            model=GEMINI_MODEL,
            user_text=user_prompt,
            system_text=system_prompt,
            response_mime_type="application/json",
            temperature=0.0,
            timeout_s=AI_TIMEOUT_S,
            max_retries=AI_MAX_RETRIES,
            log_payloads=AI_LOG_PAYLOADS,
        )
        meta["latency_ms"] = call_meta.latency_ms
        meta["retries"] = call_meta.retries
        meta["response_chars"] = len(raw_text or "")

        obj = extract_first_json_object(raw_text)

        try:
            validated2 = AISectionedMatch.model_validate(obj)
            out2 = validated2.model_dump()
            out2["education_summary"]["summary"] = _sanitize_summary(out2["education_summary"].get("summary", ""))
            out2["projects_summary"]["summary"] = _sanitize_summary(out2["projects_summary"].get("summary", ""))
            out2["work_experience_summary"]["summary"] = _sanitize_summary(out2["work_experience_summary"].get("summary", ""))
            out2["explanation"] = _sanitize_text(
                " ".join(
                    [
                        out2["education_summary"]["summary"],
                        out2["projects_summary"]["summary"],
                        out2["work_experience_summary"]["summary"],
                    ]
                ).strip(),
                1500,
            )
            out2["highlights"] = []
            out2["gaps"] = []
            meta["format"] = "sectioned_v1"
            meta["validated_schema"] = True

            if db:
                cache_match_result(
                    db,
                    out2,
                    job_id=job_id,
                    resume_id=resume_id,
                    job_text=f"{job_title or ''}\n{job_description or ''}" if not (job_id and resume_id) else None,
                    resume_text=resume_text if not (job_id and resume_id) else None,
                    api_latency_ms=call_meta.latency_ms,
                )

            return out2, meta
        except Exception:
            pass

        validated = AIMatchOutput.model_validate(obj)
        out = validated.model_dump()
        out["explanation"] = _sanitize_text(out.get("explanation", ""), 1500)
        out["highlights"] = _sanitize_list(out.get("highlights", []), 6)
        out["gaps"] = _sanitize_list(out.get("gaps", []), 6)
        meta["format"] = "legacy_v1"
        meta["validated_schema"] = True

        if db:
            cache_match_result(
                db,
                out,
                job_id=job_id,
                resume_id=resume_id,
                job_text=f"{job_title or ''}\n{job_description or ''}" if not (job_id and resume_id) else None,
                resume_text=resume_text if not (job_id and resume_id) else None,
                api_latency_ms=call_meta.latency_ms,
            )

        return out, meta
    except (ValueError, json.JSONDecodeError) as e:
        meta["warnings"].append(f"AI response parse failed: {type(e).__name__}")
        return None, meta
    except AIClientHTTPError as e:
        meta["error_code"] = int(getattr(e, "status_code", 0) or 0)
        meta["error_message"] = str(e)
        meta["warnings"].append(f"AI call failed: HTTP {meta['error_code']}")
        logger.warning("AI match failed: %s", e)
        return None, meta
    except AIClientError as e:
        logger.warning("AI match failed: %s", e)
        meta["warnings"].append(f"AI call failed: {type(e).__name__}")
        return None, meta
    except Exception as e:
        logger.exception("AI match unexpected error: %s", e)
        meta["warnings"].append("AI match failed due to unexpected error.")
        return None, meta
