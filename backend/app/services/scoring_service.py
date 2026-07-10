"""Canonical deterministic application scoring service surface."""

from .scoring_engine import compute_final_score, score_application

__all__ = ["compute_final_score", "score_application"]
