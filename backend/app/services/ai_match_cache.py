"""
AI Match Cache Service

Provides deterministic caching for AI match results.
Ensures the same resume/job combination reuses the same AI result.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models.ai_match_cache import AIMatchCache
from ..config import GEMINI_MODEL

logger = logging.getLogger(__name__)


def _generate_cache_key(
    job_id: int = None,
    resume_id: int = None,
    job_text: str = None,
    resume_text: str = None,
    model_version: str = None,
) -> str:
    """
    Generate deterministic cache key.
    Prefers database IDs if available, falls back to content hashes.
    
    Cache key: hash(job_id:resume_id:model) OR hash(job_text:resume_text:model)
    """
    model_version = model_version or GEMINI_MODEL
    
    # Primary: database IDs (most efficient)
    if job_id is not None and resume_id is not None:
        key_string = f"{job_id}:{resume_id}:{model_version}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    # Fallback: content hashes (for pre-save scenarios)
    if job_text is not None and resume_text is not None:
        job_hash = hashlib.sha256((job_text or "").encode()).hexdigest()[:32]
        resume_hash = hashlib.sha256((resume_text or "").encode()).hexdigest()[:32]
        key_string = f"{job_hash}:{resume_hash}:{model_version}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    raise ValueError("Must provide either (job_id, resume_id) or (job_text, resume_text)")


def get_cached_match(
    db: Session,
    job_id: int = None,
    resume_id: int = None,
    job_text: str = None,
    resume_text: str = None,
    model_version: str = None,
) -> dict[str, Any] | None:
    """
    Retrieve cached AI match result if exists and not expired.
    
    Args:
        Can use either database IDs or content hashes
        (job_id, resume_id, model_version) OR
        (job_text, resume_text, model_version)
    
    Returns:
        Cached match dict or None if not found/expired.
    """
    try:
        cache_key = _generate_cache_key(
            job_id=job_id,
            resume_id=resume_id,
            job_text=job_text,
            resume_text=resume_text,
            model_version=model_version,
        )
    except ValueError:
        return None
    
    try:
        cache_entry = (
            db.query(AIMatchCache)
            .filter(AIMatchCache.cache_key == cache_key)
            .first()
        )
        
        if not cache_entry:
            return None
        
        # Check expiration
        if cache_entry.expires_at and datetime.now(timezone.utc) > cache_entry.expires_at:
            logger.debug(f"Cache expired for key {cache_key[:16]}...")
            return None
        
        # Parse and return cached result
        try:
            match_result = json.loads(cache_entry.match_result_json)
            logger.debug("AI match cache hit")
            return match_result
        except json.JSONDecodeError:
            logger.warning(f"Cache corruption for key {cache_key}: invalid JSON")
            return None
            
    except Exception as e:
        logger.warning(f"Cache retrieval error: {e}")
        return None


def cache_match_result(
    db: Session,
    match_result: dict[str, Any],
    job_id: int = None,
    resume_id: int = None,
    job_text: str = None,
    resume_text: str = None,
    api_latency_ms: int = None,
    model_version: str = None,
) -> bool:
    """
    Store AI match result in cache.
    
    Args:
        Can use either database IDs or content hashes
        (job_id, resume_id, model_version) OR
        (job_text, resume_text, model_version)
    
    Returns:
        True if cached successfully, False otherwise.
    """
    try:
        cache_key = _generate_cache_key(
            job_id=job_id,
            resume_id=resume_id,
            job_text=job_text,
            resume_text=resume_text,
            model_version=model_version,
        )
    except ValueError:
        return False
    
    model_version = model_version or GEMINI_MODEL
    
    try:
        # Check if already cached
        existing = (
            db.query(AIMatchCache)
            .filter(AIMatchCache.cache_key == cache_key)
            .first()
        )
        
        if existing:
            logger.debug(f"Cache already exists for key {cache_key[:16]}...")
            return True
        
        # Store new cache entry
        cache_entry = AIMatchCache(
            cache_key=cache_key,
            job_id=job_id,
            resume_id=resume_id,
            model_version=model_version,
            match_result_json=json.dumps(match_result, ensure_ascii=False),
            api_latency_ms=api_latency_ms,
        )
        
        db.add(cache_entry)
        db.commit()
        logger.debug("AI match cache stored")
        return True
        
    except Exception as e:
        logger.warning(f"Cache storage error: {e}")
        db.rollback()
        return False
