from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from ..database import Base


class AIResumeAnalysis(Base):
    __tablename__ = "ai_resume_analyses"
    __table_args__ = (UniqueConstraint("application_id", name="uq_ai_resume_analysis_application"),)

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    candidate_summary = Column(Text, nullable=False)
    strengths_json = Column(Text, nullable=False)
    weaknesses_json = Column(Text, nullable=False)
    matched_skills_json = Column(Text, nullable=False)
    missing_skills_json = Column(Text, nullable=False)
    recommendation = Column(String(32), nullable=False)
    reasoning = Column(Text, nullable=False)
    provider = Column(String(32), nullable=False, default="gemini")
    model = Column(String(120), nullable=True)
    status = Column(String(32), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
