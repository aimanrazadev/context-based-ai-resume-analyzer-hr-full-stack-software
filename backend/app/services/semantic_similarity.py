"""
Semantic similarity utilities for resume-job matching.

This module is responsible for:
- computing cosine similarity between embedding vectors
- providing a deterministic fallback similarity path
- retrieving or creating cached embeddings for resumes and jobs
- exposing semantic matching diagnostics without breaking legacy callers
"""

import math
import json
import re
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from ..config import EMBEDDINGS_MODEL
from ..models.embedding import Embedding
from ..models.semantic_similarity_result import SemanticSimilarityResult
from .embeddings import get_or_create_embedding_details, vector_from_row


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        A float similarity score in the range [0, 1] when vectors are valid,
        otherwise 0.0.

    Side Effects:
        None.

    Error Handling:
        Returns 0.0 when vectors are empty, misaligned, or degenerate.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return float(dot / (math.sqrt(na) * math.sqrt(nb)))


_TOK_RE = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


def fallback_semantic_similarity(*, resume_text: str, job_text: str) -> float:
    """
    Compute a lightweight deterministic semantic score without embeddings.

    Args:
        resume_text: Resume text to compare.
        job_text: Job text to compare against.

    Returns:
        A fallback cosine similarity score in the range [0, 1].

    Side Effects:
        None.

    Error Handling:
        Returns 0.0 when either text is empty or tokenization produces no
        usable signal.
    """
    rt = (resume_text or "").lower()
    jt = (job_text or "").lower()
    if not rt.strip() or not jt.strip():
        return 0.0

    def toks(s: str) -> list[str]:
        out: list[str] = []
        for m in _TOK_RE.finditer(s):
            w = m.group(0)
            if w in _STOP:
                continue
            out.append(w)
        return out[:1200]

    ra = toks(rt)
    ja = toks(jt)
    if not ra or not ja:
        return 0.0

    dim = 256
    rv = [0.0] * dim
    jv = [0.0] * dim
    for w, c in Counter(ra).items():
        rv[hash(w) % dim] += float(c)
    for w, c in Counter(ja).items():
        jv[hash(w) % dim] += float(c)
    return cosine_similarity(rv, jv)


def compare_transformer_vs_keyword_matching(*, resume_text: str, job_text: str, semantic_score: float) -> dict[str, float | str]:
    """
    Compare transformer-based semantic matching against a deterministic keyword baseline.

    Args:
        resume_text: Resume text to compare.
        job_text: Job text to compare against.
        semantic_score: Already-computed transformer semantic similarity score.

    Returns:
        A small diagnostic dictionary that contrasts semantic and keyword-style
        similarity signals.

    Side Effects:
        None.

    Error Handling:
        Uses the deterministic fallback scorer as the keyword baseline and
        safely clamps the returned values.
    """
    keyword_score = fallback_semantic_similarity(resume_text=resume_text, job_text=job_text)
    semantic_clamped = max(0.0, min(1.0, float(semantic_score or 0.0)))
    keyword_clamped = max(0.0, min(1.0, float(keyword_score or 0.0)))
    return {
        "embedding_model": EMBEDDINGS_MODEL,
        "semantic_score": semantic_clamped,
        "keyword_baseline_score": keyword_clamped,
        "score_gap": round(semantic_clamped - keyword_clamped, 6),
    }


def _get_latest_embedding(db: Session, *, entity_type: str, entity_id: int, model: str) -> Embedding | None:
    """
    Fetch the latest stored embedding row for an entity and model.

    Args:
        db: Active database session.
        entity_type: Logical embedding owner type such as `resume` or `job`.
        entity_id: Database identifier for the owner entity.
        model: Embedding model name.

    Returns:
        The latest matching Embedding row, or None when not found.

    Side Effects:
        Performs a database query.

    Error Handling:
        Returns None when no row exists.
    """
    return (
        db.query(Embedding)
        .filter(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == int(entity_id),
            Embedding.model == model,
        )
        .order_by(Embedding.updated_at.desc())
        .first()
    )


def _store_similarity_result(
    db: Session,
    *,
    resume_id: int,
    job_id: int,
    model: str,
    details: dict[str, Any],
) -> None:
    """
    Persist the latest semantic similarity result for a resume-job-model tuple.

    Args:
        db: Active database session.
        resume_id: Resume database identifier.
        job_id: Job database identifier.
        model: Embedding model name.
        details: Semantic similarity diagnostics dictionary.

    Returns:
        None.

    Side Effects:
        Inserts or updates the `semantic_similarity_results` table.

    Error Handling:
        Swallows persistence failures so semantic scoring does not fail merely
        because result storage could not be updated.
    """
    try:
        comparison = details.get("comparison") if isinstance(details, dict) else {}
        row = (
            db.query(SemanticSimilarityResult)
            .filter(
                SemanticSimilarityResult.resume_id == int(resume_id),
                SemanticSimilarityResult.job_id == int(job_id),
                SemanticSimilarityResult.model == model,
            )
            .first()
        )
        payload = json.dumps(details, ensure_ascii=False)
        if row:
            row.semantic_score = float(details.get("score") or 0.0)
            row.keyword_baseline_score = float(comparison.get("keyword_baseline_score") or 0.0)
            row.score_gap = float(comparison.get("score_gap") or 0.0)
            row.used_fallback = bool(details.get("used_fallback"))
            row.fallback_reason = str(details.get("fallback_reason") or "") or None
            row.metadata_json = payload
            db.add(row)
            db.commit()
            return

        row = SemanticSimilarityResult(
            resume_id=int(resume_id),
            job_id=int(job_id),
            model=model,
            semantic_score=float(details.get("score") or 0.0),
            keyword_baseline_score=float(comparison.get("keyword_baseline_score") or 0.0),
            score_gap=float(comparison.get("score_gap") or 0.0),
            used_fallback=bool(details.get("used_fallback")),
            fallback_reason=str(details.get("fallback_reason") or "") or None,
            metadata_json=payload,
        )
        db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def resume_job_similarity_details(
    db: Session,
    *,
    resume_id: int,
    job_id: int,
    resume_text: str,
    job_text: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Compute semantic similarity plus lightweight diagnostics.

    Args:
        db: Active database session.
        resume_id: Resume database identifier.
        job_id: Job database identifier.
        resume_text: Resume text to embed or compare.
        job_text: Job text to embed or compare.
        model: Optional embedding model override.

    Returns:
        A dictionary containing the final similarity score plus diagnostics such
        as embedding availability, cache behavior, and fallback usage.

    Side Effects:
        May create or update cached embeddings in the database.

    Error Handling:
        Falls back to deterministic token-based similarity when embeddings are
        unavailable or unusable. Propagates unexpected database or embedder
        errors from the underlying embedding layer.
    """
    model_name = model or EMBEDDINGS_MODEL

    r_row, r_meta = get_or_create_embedding_details(
        db,
        entity_type="resume",
        entity_id=resume_id,
        text=resume_text,
        model=model_name,
    )
    j_row, j_meta = get_or_create_embedding_details(
        db,
        entity_type="job",
        entity_id=job_id,
        text=job_text,
        model=model_name,
    )

    if not r_row:
        r_row = _get_latest_embedding(db, entity_type="resume", entity_id=resume_id, model=model_name)
    if not j_row:
        j_row = _get_latest_embedding(db, entity_type="job", entity_id=job_id, model=model_name)

    meta: dict[str, Any] = {
        "score": 0.0,
        "model": model_name,
        "used_embeddings": False,
        "used_fallback": False,
        "resume_embedding_found": bool(r_row),
        "job_embedding_found": bool(j_row),
        "resume_embedding_meta": r_meta,
        "job_embedding_meta": j_meta,
    }

    if not r_row or not j_row:
        score = fallback_semantic_similarity(resume_text=resume_text, job_text=job_text)
        score = max(0.0, min(1.0, float(score)))
        meta["score"] = score
        meta["used_fallback"] = True
        meta["fallback_reason"] = "missing_embedding_row"
        meta["comparison"] = compare_transformer_vs_keyword_matching(
            resume_text=resume_text,
            job_text=job_text,
            semantic_score=score,
        )
        _store_similarity_result(
            db,
            resume_id=resume_id,
            job_id=job_id,
            model=model_name,
            details=meta,
        )
        return meta

    rv = vector_from_row(r_row)
    jv = vector_from_row(j_row)
    if not rv or not jv:
        score = fallback_semantic_similarity(resume_text=resume_text, job_text=job_text)
        score = max(0.0, min(1.0, float(score)))
        meta["score"] = score
        meta["used_fallback"] = True
        meta["fallback_reason"] = "invalid_stored_vector"
        meta["comparison"] = compare_transformer_vs_keyword_matching(
            resume_text=resume_text,
            job_text=job_text,
            semantic_score=score,
        )
        _store_similarity_result(
            db,
            resume_id=resume_id,
            job_id=job_id,
            model=model_name,
            details=meta,
        )
        return meta

    score = cosine_similarity(rv, jv)
    score = max(0.0, min(1.0, float(score)))
    meta["score"] = score
    meta["used_embeddings"] = True
    meta["resume_vector_dim"] = len(rv)
    meta["job_vector_dim"] = len(jv)
    meta["comparison"] = compare_transformer_vs_keyword_matching(
        resume_text=resume_text,
        job_text=job_text,
        semantic_score=score,
    )
    _store_similarity_result(
        db,
        resume_id=resume_id,
        job_id=job_id,
        model=model_name,
        details=meta,
    )
    return meta


def resume_job_similarity(
    db: Session,
    *,
    resume_id: int,
    job_id: int,
    resume_text: str,
    job_text: str,
    model: str | None = None,
) -> float:
    """
    Compute semantic similarity while preserving the legacy float-only contract.

    Args:
        db: Active database session.
        resume_id: Resume database identifier.
        job_id: Job database identifier.
        resume_text: Resume text to compare.
        job_text: Job text to compare against.
        model: Optional embedding model override.

    Returns:
        A semantic similarity score in the range [0, 1].

    Side Effects:
        May create or update cached embeddings in the database.

    Error Handling:
        Delegates to `resume_job_similarity_details` and returns only the final
        score so existing callers remain unchanged.
    """
    details = resume_job_similarity_details(
        db,
        resume_id=resume_id,
        job_id=job_id,
        resume_text=resume_text,
        job_text=job_text,
        model=model,
    )
    return float(details.get("score") or 0.0)
