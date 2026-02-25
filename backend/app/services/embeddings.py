import hashlib
import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from ..config import EMBEDDINGS_ENABLED, EMBEDDINGS_MODEL, EMBEDDINGS_PROVIDER
from ..models.embedding import Embedding


logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_EMBEDDER = None


def normalize_text(text: str) -> str:
    t = (text or "").strip()
    t = _WS_RE.sub(" ", t)
    return t


def text_hash(*, text: str, model: str) -> str:
    blob = f"{model}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(blob).hexdigest()


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    if EMBEDDINGS_PROVIDER != "local":
        raise RuntimeError("Only local embeddings are supported in this build.")
    try:
        from fastembed import TextEmbedding  # type: ignore
    except Exception as e:
        raise RuntimeError("fastembed is not installed. Install backend requirements.") from e
    _EMBEDDER = TextEmbedding(model_name=EMBEDDINGS_MODEL)
    return _EMBEDDER


def embed_text(text: str) -> list[float]:
    if not EMBEDDINGS_ENABLED:
        return []
    t = normalize_text(text)
    if not t:
        return []
    embedder = _get_embedder()
    # fastembed returns an iterator of numpy arrays
    vec = next(embedder.embed([t]))
    return [float(x) for x in vec.tolist()]


def get_or_create_embedding(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    text: str,
    model: str | None = None,
) -> Embedding | None:
    """
    Cache embeddings in DB. If the current text hash already exists, reuse it.
    If an embedding exists for the entity but the text changed, update the row.
    """
    if not EMBEDDINGS_ENABLED:
        return None

    model_name = model or EMBEDDINGS_MODEL
    norm = normalize_text(text)
    if not norm:
        return None

    h = text_hash(text=norm, model=model_name)

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
        return row

    vector = embed_text(norm)
    if not vector:
        return None

    payload = json.dumps(vector, ensure_ascii=False)
    dim = len(vector)

    if row:
        row.text_hash = h
        row.vector_json = payload
        row.dim = dim
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

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
    return row


def vector_from_row(row: Embedding) -> list[float]:
    try:
        data: Any = json.loads(row.vector_json or "[]")
        if isinstance(data, list):
            return [float(x) for x in data]
    except Exception:
        pass
    return []

