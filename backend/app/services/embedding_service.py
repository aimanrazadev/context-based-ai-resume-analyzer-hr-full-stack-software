"""Canonical local embedding service surface."""

from .embeddings import embed_text, get_or_create_embedding
from .semantic_similarity import cosine_similarity, resume_job_similarity

__all__ = ["cosine_similarity", "embed_text", "get_or_create_embedding", "resume_job_similarity"]
