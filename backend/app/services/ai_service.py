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
from ..schemas.ai_resume import AIResumeInsight
from .ai_client import AIClientError, AIClientHTTPError, gemini_generate_content
from .ai_common import extract_first_json_object

logger = logging.getLogger(__name__)

_RECOMMENDATIONS = {"Strong Fit", "Good Fit", "Average Fit", "Review Manually", "Weak Fit"}


def _fallback(*, matched_skills: list[str], missing_skills: list[str], error: str) -> tuple[dict[str, Any], dict[str, Any]]:
    matched_text = ", ".join(matched_skills[:5]) or "no confirmed required skills"
    missing_text = ", ".join(missing_skills[:5]) or "no confirmed required-skill gaps"
    payload = AIResumeInsight(
        candidate_summary=f"The candidate matches {matched_text}, but is missing {missing_text}.",
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        recommendation="Review Manually",
        reasoning="AI analysis was unavailable, so the recruiter should review the deterministic evidence.",
    ).model_dump()
    return payload, {"status": "fallback", "error_message": error, "model": GEMINI_MODEL}


async def analyze_resume_for_job(
    *,
    structured_resume: dict[str, Any],
    job_title: str,
    job_description: str,
    required_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate validated human-readable insights without asking AI for a numeric score."""
    if not GEMINI_API_KEY:
        return _fallback(matched_skills=matched_skills, missing_skills=missing_skills, error="AI provider is not configured.")

    compact_input = {
        "job": {
            "title": job_title,
            "description": job_description,
            "required_skills": required_skills,
        },
        "candidate": structured_resume,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }
    prompt = (
        "Analyze the supplied factual candidate data against the job. Do not calculate or output a numeric score. "
        "Do not invent evidence. Return only JSON with this exact shape: "
        '{"candidate_summary":string,"strengths":string[],"weaknesses":string[],'
        '"matched_skills":string[],"missing_skills":string[],"recommendation":string,"reasoning":string}. '
        "The recommendation must be exactly one of: Strong Fit, Good Fit, Average Fit, Review Manually, Weak Fit. "
        "The candidate summary must mention matched skills, then use the word 'but' before missing skills.\n\n"
        + json.dumps(compact_input, ensure_ascii=False)
    )
    meta: dict[str, Any] = {"status": "success", "model": GEMINI_MODEL, "generated_at": datetime.now(timezone.utc).isoformat()}
    try:
        raw, call_meta = await gemini_generate_content(
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
            api_version=GEMINI_API_VERSION,
            model=GEMINI_MODEL,
            user_text=prompt,
            system_text="You are an evidence-based recruiting assistant. Return valid JSON only.",
            response_mime_type="application/json",
            temperature=0.0,
            timeout_s=AI_TIMEOUT_S,
            max_retries=AI_MAX_RETRIES,
            log_payloads=AI_LOG_PAYLOADS,
        )
        payload = AIResumeInsight.model_validate(extract_first_json_object(raw)).model_dump()
        if payload["recommendation"] not in _RECOMMENDATIONS:
            payload["recommendation"] = "Review Manually"
        payload["matched_skills"] = matched_skills
        payload["missing_skills"] = missing_skills
        meta.update({"latency_ms": call_meta.latency_ms, "retries": call_meta.retries, "validated_schema": True})
        logger.info("AI resume analysis completed model=%s latency_ms=%s", GEMINI_MODEL, call_meta.latency_ms)
        return payload, meta
    except (AIClientError, AIClientHTTPError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("AI resume analysis failed: %s", exc)
        return _fallback(matched_skills=matched_skills, missing_skills=missing_skills, error=str(exc))
