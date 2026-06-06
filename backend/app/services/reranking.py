"""
Cross-encoder reranking utilities for recruiter-facing candidate ranking.

This module is responsible for:
- building a shortlist from embedding-based candidate retrieval
- reranking shortlisted candidates with a cross-encoder transformer
- comparing reranked order against cosine-similarity retrieval
- exposing lightweight diagnostics without changing the rest of the ranking flow
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import math
from typing import Any

from ..config import (
    RERANKER_ENABLED,
    RERANKER_MODEL,
    RERANKER_SHORTLIST_SIZE,
    RERANKER_TIMEOUT_S,
)


_RERANKER = None


def _sigmoid(value: float) -> float:
    """
    Convert an unbounded reranker score into a stable 0-1 score.

    Args:
        value: Raw cross-encoder output score.

    Returns:
        A normalized score in the range [0, 1].

    Side Effects:
        None.

    Error Handling:
        Handles very large positive or negative values without overflow.
    """
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _ensure_reranker_cached_locally() -> str | None:
    """
    Check whether the configured reranker model already exists in the local HF cache.

    Returns:
        The cached snapshot path when available, otherwise None.

    Side Effects:
        None.

    Error Handling:
        Returns None when huggingface_hub is unavailable or when the model has
        not been downloaded yet.
    """
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception:
        return None

    try:
        path = snapshot_download(repo_id=RERANKER_MODEL, local_files_only=True)
    except Exception:
        return None
    return str(path) if path else None


def _get_reranker():
    """
    Lazily initialize the local cross-encoder reranker.

    Returns:
        A `sentence_transformers.CrossEncoder` instance.

    Side Effects:
        Caches the reranker model in module state.

    Error Handling:
        Raises `RuntimeError` when reranking is disabled or dependencies are
        missing.
    """
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER
    if not RERANKER_ENABLED:
        raise RuntimeError("Reranking is disabled.")
    cached_path = _ensure_reranker_cached_locally()
    if not cached_path:
        raise RuntimeError(
            "Reranker model is not cached locally yet. Warm it once before enabling request-time reranking."
        )
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Install backend requirements."
        ) from exc
    _RERANKER = CrossEncoder(cached_path)
    return _RERANKER


def _predict_with_timeout(*, pairs: list[tuple[str, str]]) -> list[float]:
    """
    Load the reranker and score candidate pairs within a bounded timeout.

    Args:
        pairs: `(job_text, candidate_text)` tuples for cross-encoder scoring.

    Returns:
        A list of raw reranker scores.

    Side Effects:
        Initializes the reranker model lazily in a worker thread.

    Error Handling:
        Raises `TimeoutError` when model loading or inference exceeds the
        configured timeout window.
    """
    def _run() -> list[float]:
        reranker = _get_reranker()
        raw_scores = reranker.predict(pairs)
        return [float(score) for score in raw_scores]

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run)
    try:
        return future.result(timeout=max(1.0, float(RERANKER_TIMEOUT_S)))
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(
            f"Reranker exceeded timeout of {float(RERANKER_TIMEOUT_S):.1f}s."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def build_rerank_text(
    *,
    extracted_text: str | None,
    structured_sections: dict[str, Any] | None = None,
    ai_analysis: dict[str, Any] | None = None,
) -> str:
    """
    Build a concise candidate profile text for reranking.

    Args:
        extracted_text: Clean extracted resume text.
        structured_sections: Deterministic or AI-structured resume sections.
        ai_analysis: Optional AI resume analysis block.

    Returns:
        A compact text string representing the candidate.

    Side Effects:
        None.

    Error Handling:
        Ignores malformed section structures and falls back to extracted text.
    """
    parts: list[str] = []
    sections = structured_sections or {}
    for key in ("skills", "experience", "projects", "education", "certifications"):
        section = sections.get(key) if isinstance(sections, dict) else None
        if not isinstance(section, dict):
            continue
        text = str(section.get("text") or "").strip()
        if text:
            parts.append(f"{key.title()}: {text}")
            continue
        items = section.get("items")
        if isinstance(items, list) and items:
            rendered = []
            for item in items[:6]:
                if isinstance(item, dict):
                    rendered.append(str(item.get("summary") or item.get("name") or "").strip())
                else:
                    rendered.append(str(item).strip())
            rendered = [chunk for chunk in rendered if chunk]
            if rendered:
                parts.append(f"{key.title()}: {'; '.join(rendered)}")

    if isinstance(ai_analysis, dict):
        recruiter_summary = str(ai_analysis.get("recruiter_summary") or "").strip()
        candidate_summary = str(ai_analysis.get("candidate_summary") or "").strip()
        strengths = ai_analysis.get("strengths")
        missing_skills = ai_analysis.get("missing_skills")
        if recruiter_summary:
            parts.append(f"Recruiter summary: {recruiter_summary}")
        elif candidate_summary:
            parts.append(f"Candidate summary: {candidate_summary}")
        if isinstance(strengths, list) and strengths:
            parts.append("Strengths: " + "; ".join(str(x).strip() for x in strengths[:5] if str(x).strip()))
        if isinstance(missing_skills, list) and missing_skills:
            parts.append("Missing skills: " + ", ".join(str(x).strip() for x in missing_skills[:5] if str(x).strip()))

    fallback_text = str(extracted_text or "").strip()
    if fallback_text:
        parts.append(fallback_text[:2500])

    return "\n".join(part for part in parts if part).strip()


def rerank_candidate_shortlist(
    *,
    job_text: str,
    candidates: list[dict[str, Any]],
    shortlist_size: int | None = None,
) -> dict[str, Any]:
    """
    Rerank a shortlist of candidates using a cross-encoder transformer.

    Args:
        job_text: Combined job title and description text.
        candidates: Candidate dictionaries containing `application_id`,
            `semantic_score`, and `rerank_text`.
        shortlist_size: Optional shortlist size override.

    Returns:
        A dictionary containing reranking metadata and per-application scores.

    Side Effects:
        Runs local transformer inference when enabled.

    Error Handling:
        Returns a graceful disabled/failed payload instead of raising when
        reranking cannot be completed.
    """
    shortlist_n = max(1, int(shortlist_size or RERANKER_SHORTLIST_SIZE or 8))
    usable = [
        c
        for c in (candidates or [])
        if c.get("application_id") is not None and str(c.get("rerank_text") or "").strip()
    ]
    usable.sort(key=lambda item: float(item.get("semantic_score") or 0.0), reverse=True)
    shortlist = usable[:shortlist_n]

    result: dict[str, Any] = {
        "enabled": bool(RERANKER_ENABLED),
        "model": RERANKER_MODEL,
        "shortlist_size": shortlist_n,
        "shortlisted_application_ids": [int(item["application_id"]) for item in shortlist],
        "per_application": {},
    }
    if not RERANKER_ENABLED:
        result["reason"] = "disabled"
        return result
    if not shortlist or not str(job_text or "").strip():
        result["reason"] = "insufficient_inputs"
        return result

    try:
        pairs = [(job_text, str(item.get("rerank_text") or "")) for item in shortlist]
        raw_scores = _predict_with_timeout(pairs=pairs)
    except Exception as exc:
        err_type = type(exc).__name__
        if isinstance(exc, TimeoutError):
            result["reason"] = "reranker_timeout"
            result["timeout_s"] = float(RERANKER_TIMEOUT_S)
        else:
            msg = str(exc).lower()
            if "not cached locally" in msg:
                result["reason"] = "reranker_model_not_cached"
            elif err_type == "OSError":
                result["reason"] = "reranker_unavailable"
            else:
                result["reason"] = f"reranker_error:{err_type}"
        return result

    scored = []
    for item, raw_score in zip(shortlist, raw_scores):
        raw_value = float(raw_score)
        normalized = _sigmoid(raw_value)
        scored.append(
            {
                "application_id": int(item["application_id"]),
                "semantic_score": float(item.get("semantic_score") or 0.0),
                "raw_score": raw_value,
                "normalized_score": normalized,
            }
        )

    semantic_order = sorted(scored, key=lambda item: item["semantic_score"], reverse=True)
    reranked_order = sorted(scored, key=lambda item: item["normalized_score"], reverse=True)
    semantic_rank_map = {item["application_id"]: idx + 1 for idx, item in enumerate(semantic_order)}
    reranked_rank_map = {item["application_id"]: idx + 1 for idx, item in enumerate(reranked_order)}

    per_application: dict[str, Any] = {}
    for item in reranked_order:
        app_id = item["application_id"]
        semantic_rank = semantic_rank_map.get(app_id)
        reranked_rank = reranked_rank_map.get(app_id)
        per_application[str(app_id)] = {
            "semantic_shortlist_rank": semantic_rank,
            "reranked_shortlist_rank": reranked_rank,
            "rank_delta": (semantic_rank - reranked_rank) if semantic_rank and reranked_rank else 0,
            "reranker_raw_score": round(item["raw_score"], 6),
            "reranker_score": round(item["normalized_score"], 6),
            "semantic_score": round(float(item["semantic_score"]), 6),
            "comparison": {
                "reranker_score": round(item["normalized_score"], 6),
                "cosine_similarity_score": round(float(item["semantic_score"]), 6),
                "score_gap": round(float(item["normalized_score"]) - float(item["semantic_score"]), 6),
            },
        }
    result["per_application"] = per_application
    result["reason"] = "ok"
    return result
