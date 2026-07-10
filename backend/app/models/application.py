from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
        Index("ix_applications_job_final_score", "job_id", "final_score"),
        Index("ix_applications_candidate_created", "candidate_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    ai_explanation = Column(Text)
    # Canonical backend scoring record.
    semantic_score = Column(Float, nullable=True)
    skills_score = Column(Float, nullable=True)
    experience_score = Column(Float, nullable=True)
    ai_score = Column(Float, nullable=True)
    final_score = Column(Integer, nullable=True)  # 0-100
    score_breakdown_json = Column(Text, nullable=True)
    matched_skills_json = Column(Text, nullable=True)
    missing_skills_json = Column(Text, nullable=True)
    ranking_explanation = Column(Text, nullable=True)
    score_updated_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    resume = relationship("Resume")

