import math
import re
from collections import Counter

from sqlalchemy.orm import Session

from ..config import EMBEDDINGS_MODEL
from ..models.embedding import Embedding
from .embeddings import get_or_create_embedding, vector_from_row


def cosine_similarity(a: list[float], b: list[float]) -> float:
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
    Lightweight fallback when embeddings aren't available.
    Uses a hashing trick + cosine similarity over token counts.
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

    # Hashing trick into fixed dimension.
    dim = 256
    rv = [0.0] * dim
    jv = [0.0] * dim
    for w, c in Counter(ra).items():
        rv[hash(w) % dim] += float(c)
    for w, c in Counter(ja).items():
        jv[hash(w) % dim] += float(c)
    return cosine_similarity(rv, jv)


def _get_latest_embedding(db: Session, *, entity_type: str, entity_id: int, model: str) -> Embedding | None:
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


def resume_job_similarity(
    db: Session,
    *,
    resume_id: int,
    job_id: int,
    resume_text: str,
    job_text: str,
    model: str | None = None,
) -> float:
    model_name = model or EMBEDDINGS_MODEL

    r_row = get_or_create_embedding(db, entity_type="resume", entity_id=resume_id, text=resume_text, model=model_name)
    j_row = get_or_create_embedding(db, entity_type="job", entity_id=job_id, text=job_text, model=model_name)

    # If embeddings are disabled or text empty, try whatever is already present.
    if not r_row:
        r_row = _get_latest_embedding(db, entity_type="resume", entity_id=resume_id, model=model_name)
    if not j_row:
        j_row = _get_latest_embedding(db, entity_type="job", entity_id=job_id, model=model_name)

    if not r_row or not j_row:
        # Embeddings not available (e.g., first-run download issues). Fall back to token-based similarity.
        score = fallback_semantic_similarity(resume_text=resume_text, job_text=job_text)
        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return float(score)

    rv = vector_from_row(r_row)
    jv = vector_from_row(j_row)
    score = cosine_similarity(rv, jv)
    # Clamp just in case of float noise
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score

