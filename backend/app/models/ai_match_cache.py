from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from ..database import Base


class AIMatchCache(Base):
    """
    Caches AI match results for deterministic scoring.
    Key: sha256(job_id + resume_id + model_version)
    Prevents duplicate API calls for the same resume/job combination.
    """
    __tablename__ = "ai_match_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(128), unique=True, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)
    resume_id = Column(Integer, nullable=False, index=True)
    model_version = Column(String(50), default="gemini-2.0-flash", nullable=False)
    
    # Cached match result
    match_result_json = Column(Text, nullable=False)  # Full match dict as JSON
    match_score = Column(Integer, nullable=True)  # 0-100
    
    # Metadata
    api_latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For cache invalidation

    def __repr__(self) -> str:
        return f"<AIMatchCache(key={self.cache_key[:16]}..., job={self.job_id}, resume={self.resume_id})>"
