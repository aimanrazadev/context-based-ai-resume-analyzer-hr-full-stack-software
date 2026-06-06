import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import (
    AI_LOG_PAYLOADS,
    AI_MAX_RETRIES,
    AI_TIMEOUT_S,
    GEMINI_API_KEY,
    GEMINI_API_VERSION,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
)
from ..schemas.ai_resume import AIResumeStructured
from .ai_client import AIClientError, AIClientHTTPError, gemini_generate_content
from .ai_common import extract_first_json_object
from .ai_prompts import resume_structuring_system_prompt, resume_structuring_user_prompt


logger = logging.getLogger(__name__)


def _truncate_list(items: list[str], n: int) -> list[str]:
    """
    Truncate a list to a fixed maximum size.

    Args:
        items: Source list to shorten.
        n: Maximum number of items to keep.

    Returns:
        A truncated copy of the list.

    Side Effects:
        None.

    Error Handling:
        Treats falsy inputs as empty lists.
    """
    return list(items or [])[:n]


def _sanitize_text(s: str, max_len: int = 8000) -> str:
    """
    Normalize and cap AI-generated text before storage.

    Args:
        s: Raw model output text.
        max_len: Maximum number of characters to keep.

    Returns:
        A cleaned string safe for storage in DB text fields.

    Side Effects:
        None.

    Error Handling:
        Treats falsy inputs as empty strings.
    """
    s = s or ""
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _sanitize_label(s: str, max_len: int = 32) -> str:
    """
    Normalize and cap short label-like AI output values.

    Args:
        s: Raw model-generated short label.
        max_len: Maximum number of characters to keep.

    Returns:
        A lowercase underscore-friendly label candidate.

    Side Effects:
        None.

    Error Handling:
        Treats falsy inputs as empty strings.
    """
    s = _sanitize_text(s or "", max_len=max_len).lower()
    s = s.replace(" ", "_")
    return s


async def ai_structure_resume(*, resume_text: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Generate AI-structured resume output using Gemini.

    Args:
        resume_text: Clean resume text from the extraction pipeline.

    Returns:
        A tuple containing:
        - validated structured resume data or None
        - metadata with warnings, timing, schema validation, and model details

    Side Effects:
        Performs an outbound AI call when Gemini is configured and logs warning
        or exception details.

    Error Handling:
        Returns `(None, meta)` on parse, validation, HTTP, network, or
        unexpected failures instead of raising to the upload flow.
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

    user_prompt = resume_structuring_user_prompt(resume_text=resume_text or "")
    system_prompt = resume_structuring_system_prompt()

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
        validated = AIResumeStructured.model_validate(obj)
        out = validated.model_dump()

        out["version"] = max(3, int(out.get("version") or 3))
        out["sections"]["skills"]["text"] = _sanitize_text(out["sections"]["skills"].get("text", ""), 5000)
        out["sections"]["experience"]["text"] = _sanitize_text(out["sections"]["experience"].get("text", ""), 8000)
        out["sections"]["projects"]["text"] = _sanitize_text(out["sections"]["projects"].get("text", ""), 6000)
        out["sections"]["education"]["text"] = _sanitize_text(out["sections"]["education"].get("text", ""), 4000)
        out["sections"]["skills"]["items"] = _truncate_list(out["sections"]["skills"].get("items", []), 80)
        out["sections"]["skills"]["primary"] = _truncate_list(out["sections"]["skills"].get("primary", []), 20)
        out["sections"]["skills"]["secondary"] = _truncate_list(out["sections"]["skills"].get("secondary", []), 60)
        out["sections"]["experience"]["bullets"] = _truncate_list(out["sections"]["experience"].get("bullets", []), 30)
        out["sections"]["projects"]["items"] = _truncate_list(out["sections"]["projects"].get("items", []), 20)
        out["sections"]["education"]["items"] = _truncate_list(out["sections"]["education"].get("items", []), 20)
        out["analysis"]["candidate_summary"] = _sanitize_text(out["analysis"].get("candidate_summary", ""), 700)
        out["analysis"]["recruiter_summary"] = _sanitize_text(out["analysis"].get("recruiter_summary", ""), 500)
        out["analysis"]["strengths"] = _truncate_list(out["analysis"].get("strengths", []), 5)
        out["analysis"]["weaknesses"] = _truncate_list(out["analysis"].get("weaknesses", []), 5)
        out["analysis"]["missing_skills"] = _truncate_list(out["analysis"].get("missing_skills", []), 8)
        out["analysis"]["hiring_recommendation"] = _sanitize_label(
            out["analysis"].get("hiring_recommendation", ""),
            24,
        )
        out["raw"]["warnings"] = _truncate_list(out.get("raw", {}).get("warnings", []), 20)
        meta["validated_schema"] = True

        return out, meta
    except (ValueError, json.JSONDecodeError) as e:
        meta["warnings"].append(f"AI response parse failed: {type(e).__name__}")
        return None, meta
    except AIClientHTTPError as e:
        meta["error_code"] = int(getattr(e, "status_code", 0) or 0)
        meta["error_message"] = str(e)
        meta["warnings"].append(f"AI call failed: HTTP {meta['error_code']}")
        logger.warning("AI structuring failed: %s", e)
        return None, meta
    except AIClientError as e:
        logger.warning("AI structuring failed: %s", e)
        meta["warnings"].append(f"AI call failed: {type(e).__name__}")
        return None, meta
    except Exception as e:
        logger.exception("AI structuring unexpected error: %s", e)
        meta["warnings"].append("AI structuring failed due to unexpected error.")
        return None, meta
