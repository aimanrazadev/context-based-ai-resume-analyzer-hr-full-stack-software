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
    GEMINI_FALLBACK_MODELS,
    GEMINI_MODEL,
)
from ..schemas.ai_resume import AIResumeInsight
from .ai_client import AIClientError, AIClientHTTPError, gemini_generate_content
from .ai_common import extract_first_json_object

logger = logging.getLogger(__name__)

_RECOMMENDATIONS = {"Strong Fit", "Good Fit", "Average Fit", "Review Manually", "Weak Fit"}
_AI_EXPLANATION_FALLBACK_MESSAGE = "AI explanation could not be generated. The match score is still available."
_TRANSIENT_AI_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MODEL_UNAVAILABLE_STATUS_CODES = {404}


def _model_candidates() -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for value in [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]:
        model = str(value or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        candidates.append(model)
    return candidates


def _fallback(*, matched_skills: list[str], missing_skills: list[str], error: str) -> tuple[dict[str, Any], dict[str, Any]]:
    matched_text = ", ".join(matched_skills[:5]) or "no confirmed required skills"
    missing_text = ", ".join(missing_skills[:5]) or "no confirmed required-skill gaps"
    payload = AIResumeInsight(
        candidate_summary="Candidate background summary is unavailable because AI analysis could not be completed.",
        strengths=[f"Matched required skills: {matched_text}."] if matched_skills else [],
        weaknesses=[f"Missing or unclear required skills: {missing_text}."] if missing_skills else ["No major required-skill gaps detected from deterministic matching."],
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        recommendation="Review Manually",
        strength_reasoning="AI analysis was unavailable, so strengths should be verified from deterministic matched skills and resume evidence.",
        weakness_reasoning="AI analysis was unavailable, so missing skills should be verified during recruiter review.",
        reasoning="AI analysis was unavailable, so the recruiter should review the deterministic evidence.",
    ).model_dump()
    return payload, {
        "status": "fallback",
        "error_message": _AI_EXPLANATION_FALLBACK_MESSAGE,
        "internal_error_message": error,
        "model": GEMINI_MODEL,
    }


async def analyze_resume_for_job(
    *,
    structured_resume: dict[str, Any],
    resume_text: str | None = None,
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
        "resume_text": (resume_text or "")[:12000],
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }
    prompt = (
        "Analyze the supplied factual candidate data against the job. Do not calculate or output a numeric score. "
        "Use only evidence from the candidate data, matched skills, missing skills, and job description. "
        "Do not invent candidate experience, impact, education, or weaknesses. "
        "Return only JSON with this exact shape: "
        '{"candidate_summary":string,"strengths":string[],"weaknesses":string[],'
        '"strength_reasoning":string,"weakness_reasoning":string,'
        '"matched_skills":string[],"missing_skills":string[],"recommendation":string,"reasoning":string}. '
        "The recommendation must be exactly one of: Strong Fit, Good Fit, Average Fit, Review Manually, Weak Fit. "
        "candidate_summary rules: maximum 2 concise lines and factual only. Do not include recommendations, hiring decisions, "
        "strengths, weaknesses, or suitability. Summarize only the candidate background: primary profile "
        "(for example Full-Stack Developer, AI/ML Engineer, Backend Developer), major project names, primary technology stack, "
        "education including college/university name and CGPA/percentage if present, and professional experience including company "
        "names, job titles, and measurable impact/contributions if present. Omit missing facts; do not invent them. "
        "Do not repeat information shown elsewhere or list the whole resume. "
        "strengths rules: short evidence chips only, not paragraphs; include only demonstrated strengths relevant to the job. "
        "weaknesses rules: short chips only; include only genuine missing or weak areas from required job skills/experience; "
        "do not invent weaknesses if the resume demonstrates the requirement. "
        "strength_reasoning rules: max 2 short paragraphs, each around 2-3 lines, explaining project/experience evidence, matched skills, system impact, and job alignment. "
        "weakness_reasoning rules: max 2 short paragraphs, each around 2-3 lines, explaining only genuine missing or unclear requirements, severity, and what to verify in interview; if no meaningful gaps exist, say that briefly. "
        "reasoning rules: max 2 short paragraphs, each around 2-3 lines, connecting the candidate's projects, skills, experience/education, and overall fit without repeating candidate_summary verbatim.\n\n"
        + json.dumps(compact_input, ensure_ascii=False)
    )
    meta: dict[str, Any] = {"status": "success", "model": GEMINI_MODEL, "generated_at": datetime.now(timezone.utc).isoformat()}
    last_error: Exception | None = None
    for index, model in enumerate(_model_candidates()):
        try:
            raw, call_meta = await gemini_generate_content(
                api_key=GEMINI_API_KEY,
                base_url=GEMINI_BASE_URL,
                api_version=GEMINI_API_VERSION,
                model=model,
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
            meta.update(
                {
                    "model": call_meta.model or model,
                    "latency_ms": call_meta.latency_ms,
                    "retries": call_meta.retries,
                    "validated_schema": True,
                    "fallback_model_used": index > 0,
                }
            )
            logger.info("AI resume analysis completed model=%s latency_ms=%s", meta["model"], call_meta.latency_ms)
            return payload, meta
        except AIClientHTTPError as exc:
            last_error = exc
            can_try_next = index < len(_model_candidates()) - 1
            should_try_next = exc.status_code in (_TRANSIENT_AI_STATUS_CODES | _MODEL_UNAVAILABLE_STATUS_CODES) and can_try_next
            if should_try_next:
                logger.warning("AI model %s failed with HTTP %s; trying fallback model", model, exc.status_code)
                continue
            logger.warning("AI resume analysis failed: %s", exc)
            break
        except AIClientError as exc:
            last_error = exc
            if index < len(_model_candidates()) - 1:
                logger.warning("AI model %s failed with %s; trying fallback model", model, type(exc).__name__)
                continue
            logger.warning("AI resume analysis failed: %s", exc)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if index < len(_model_candidates()) - 1:
                logger.warning("AI model %s returned invalid JSON; trying fallback model", model)
                continue
            logger.warning("AI resume analysis failed: %s", exc)
            break

    return _fallback(
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        error=str(last_error or "AI provider failed."),
    )
