from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from ..database import Base


class SemanticSimilarityResult(Base):
    __tablename__ = "semantic_similarity_results"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)
    model = Column(String(120), nullable=False)
    semantic_score = Column(Float, nullable=False, default=0.0)
    keyword_baseline_score = Column(Float, nullable=True)
    score_gap = Column(Float, nullable=True)
    used_fallback = Column(Boolean, nullable=False, default=False)
    fallback_reason = Column(String(80), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", "model", name="uq_semantic_similarity_resume_job_model"),
    )
