"""
Embedding generation and persistence utilities.

This module is responsible for:
- normalizing text before embedding
- generating local transformer embeddings
- caching embeddings in the database
- reusing embeddings when the source text has not changed
- exposing lightweight diagnostics for downstream semantic matching
"""

import hashlib
import json
import logging
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from ..config import EMBEDDINGS_ENABLED, EMBEDDINGS_MODEL, EMBEDDINGS_PROVIDER
from ..models.embedding import Embedding


logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_EMBEDDER = None
_EMBEDDER_FAILED = False
_MAX_EMBED_TEXT_CHARS = 12000


def normalize_text(text: str) -> str:
    """
    Normalize free-form text before hashing or embedding.
    """
    t = (text or "").strip()
    t = _WS_RE.sub(" ", t)
    return t


def truncate_for_embedding(*, text: str, max_chars: int = _MAX_EMBED_TEXT_CHARS) -> str:
    """
    Limit input text length before embedding to keep local inference practical.
    """
    t = normalize_text(text)
    if len(t) <= max_chars:
        return t
    return t[:max_chars].strip()


def text_hash(*, text: str, model: str) -> str:
    """
    Compute a stable content hash for an embedding input.
    """
    blob = f"{model}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(blob).hexdigest()


def _get_embedder():
    """
    Lazily initialize the local embedding model instance.

    Uses `sentence-transformers` as the primary local transformer embedding
    stack and keeps the same external interface for the rest of the backend.
    """
    global _EMBEDDER, _EMBEDDER_FAILED
    if _EMBEDDER is not None:
        return _EMBEDDER
    if _EMBEDDER_FAILED:
        raise RuntimeError("Local embedding model is unavailable.")
    if EMBEDDINGS_PROVIDER != "local":
        raise RuntimeError("Only local embeddings are supported in this build.")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as e:
        _EMBEDDER_FAILED = True
        raise RuntimeError(
            "sentence-transformers is not installed. Install backend requirements."
        ) from e
    try:
        _EMBEDDER = SentenceTransformer(EMBEDDINGS_MODEL, local_files_only=True)
    except TypeError:
        _EMBEDDER = SentenceTransformer(EMBEDDINGS_MODEL)
    except Exception as e:
        _EMBEDDER_FAILED = True
        raise RuntimeError("Local embedding model is unavailable. Semantic score will fall back to 0.") from e
    return _EMBEDDER


def embed_text(text: str) -> list[float]:
    """
    Generate a local transformer embedding vector for the given text.

    Uses the Sentence Transformers stack with the configured embedding model.
    """
    if not EMBEDDINGS_ENABLED:
        return []
    t = truncate_for_embedding(text=text)
    if not t:
        return []
    embedder = _get_embedder()
    try:
        vec = embedder.encode(t, convert_to_numpy=True, normalize_embeddings=True)
    except TypeError:
        # Some versions may not support all kwargs in the exact same way.
        vec = embedder.encode(t)
    return [float(x) for x in vec.tolist()]


def get_or_create_embedding_details(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    text: str,
    model: str | None = None,
) -> tuple[Embedding | None, dict[str, Any]]:
    """
    Fetch or create an embedding row with lightweight diagnostics.
    """
    meta: dict[str, Any] = {
        "enabled": bool(EMBEDDINGS_ENABLED),
        "provider": EMBEDDINGS_PROVIDER,
        "model": model or EMBEDDINGS_MODEL,
        "entity_type": entity_type,
        "entity_id": int(entity_id),
        "embedding_library": "sentence-transformers",
        "cache_hit": False,
        "updated_existing": False,
        "created_new": False,
        "text_was_truncated": False,
        "failure_reason": None,
    }
    if not EMBEDDINGS_ENABLED:
        meta["failure_reason"] = "embeddings_disabled"
        return None, meta

    model_name = model or EMBEDDINGS_MODEL
    norm = normalize_text(text)
    truncated = truncate_for_embedding(text=norm)
    meta["normalized_text_chars"] = len(norm)
    meta["embedded_text_chars"] = len(truncated)
    meta["text_was_truncated"] = len(truncated) < len(norm)
    if not truncated:
        meta["failure_reason"] = "empty_text"
        return None, meta

    h = text_hash(text=truncated, model=model_name)
    meta["text_hash"] = h

    row = (
        db.query(Embedding)
        .filter(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == int(entity_id),
            Embedding.model == model_name,
        )
        .order_by(Embedding.updated_at.desc())
        .first()
    )

    if row and row.text_hash == h and row.vector_json:
        meta["cache_hit"] = True
        meta["vector_dim"] = int(row.dim or 0)
        return row, meta

    try:
        vector = embed_text(truncated)
    except Exception as e:
        meta["failure_reason"] = f"embedder_error:{type(e).__name__}"
        raise

    if not vector:
        meta["failure_reason"] = "empty_vector"
        return None, meta

    payload = json.dumps(vector, ensure_ascii=False)
    dim = len(vector)
    meta["vector_dim"] = dim

    if row:
        row.text_hash = h
        row.vector_json = payload
        row.dim = dim
        db.add(row)
        db.commit()
        db.refresh(row)
        meta["updated_existing"] = True
        return row, meta

    row = Embedding(
        entity_type=entity_type,
        entity_id=int(entity_id),
        model=model_name,
        dim=dim,
        text_hash=h,
        vector_json=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    meta["created_new"] = True
    return row, meta


def get_or_create_embedding(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    text: str,
    model: str | None = None,
) -> Embedding | None:
    """
    Fetch or create an embedding row while preserving the legacy return shape.
    """
    row, _meta = get_or_create_embedding_details(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        text=text,
        model=model,
    )
    return row


def vector_from_row(row: Embedding) -> list[float]:
    """
    Deserialize an embedding vector from a database row.
    """
    try:
        data: Any = json.loads(row.vector_json or "[]")
        if isinstance(data, list):
            return [float(x) for x in data]
    except Exception:
        pass
    return []
