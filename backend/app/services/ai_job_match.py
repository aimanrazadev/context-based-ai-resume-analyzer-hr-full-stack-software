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
    return [str(x).strip() for x in (items or []) if str(x).strip()][:n]


def _sanitize_text(s: str, max_len: int = 1200) -> str:
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def _sanitize_summary(s: str, max_len: int = 220) -> str:
    s = (s or "").strip()
    # Keep to ~2 sentences max
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", s) if p.strip()]
    s2 = " ".join(parts[:2]) if parts else s
    if len(s2) > max_len:
        return s2[:max_len] + "…"
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
    Returns (match_dict_or_none, meta).
    match_dict shape: {score(int 0-100), explanation(str), highlights(list), gaps(list)}
    
    Args:
        job_title, job_description, resume_text: Content to match
        db: Optional database session for caching
        job_id, resume_id: Optional for cache lookup by ID (requires db)
    
    If db and both job_id/resume_id provided, checks cache first.
    If cache hit, returns cached result immediately.
    """
    meta: dict[str, Any] = {
        "enabled": bool(GEMINI_API_KEY),
        "warnings": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": GEMINI_MODEL,
    }
    if not GEMINI_API_KEY:
        meta["warnings"].append("AI disabled: GEMINI_API_KEY not configured.")
        return None, meta

    # Check cache first
    if db and job_id and resume_id:
        cached = get_cached_match(db, job_id=job_id, resume_id=resume_id)
        if cached:
            meta["from_cache"] = True
            meta["cached_hit"] = True
            return cached, meta

    # Fallback: cache by content hash for pre-save scenarios
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

    # Prefer sectioned output (better UX); fall back to legacy shape if parsing fails.
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

        obj = extract_first_json_object(raw_text)

        # Try new sectioned format first
        try:
            validated2 = AISectionedMatch.model_validate(obj)
            out2 = validated2.model_dump()
            out2["education_summary"]["summary"] = _sanitize_summary(out2["education_summary"].get("summary", ""))
            out2["projects_summary"]["summary"] = _sanitize_summary(out2["projects_summary"].get("summary", ""))
            out2["work_experience_summary"]["summary"] = _sanitize_summary(out2["work_experience_summary"].get("summary", ""))

            # Back-compat: expose score/explanation as well.
            out2["score"] = int(out2.get("overall_match_score") or 0)
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
            
            # Cache successful result
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

        # Legacy fallback
        validated = AIMatchOutput.model_validate(obj)
        out = validated.model_dump()
        out["explanation"] = _sanitize_text(out.get("explanation", ""), 1500)
        out["highlights"] = _sanitize_list(out.get("highlights", []), 6)
        out["gaps"] = _sanitize_list(out.get("gaps", []), 6)
        meta["format"] = "legacy_v1"
        
        # Cache successful result
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
        # Surface HTTP error info to callers so UI can react (e.g., quota exhausted).
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

