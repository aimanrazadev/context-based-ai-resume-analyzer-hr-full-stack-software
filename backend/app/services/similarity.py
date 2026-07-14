"""
Semantic similarity utilities for resume-job matching.

This module is responsible for:
- computing cosine similarity between embedding vectors
"""

import math


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
