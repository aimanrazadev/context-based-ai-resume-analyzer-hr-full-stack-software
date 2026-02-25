from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    # Legacy transcript/scoring fields (kept, but AI screening flow removed)
    transcript = Column(Text, nullable=True)
    clarity_score = Column(Float, nullable=True)
    relevance_score = Column(Float, nullable=True)
    overall_fit = Column(Float, nullable=True)

    # Lifecycle: scheduled -> completed -> evaluated (optional cancelled)
    status = Column(String(32), nullable=True)  # scheduled | completed | evaluated | cancelled

    # Scheduling (full set)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # stored in UTC
    timezone = Column(String(64), nullable=True)  # e.g. Asia/Kolkata
    duration_minutes = Column(Integer, nullable=True)
    mode = Column(String(32), nullable=True)  # Zoom | Phone | In-person
    meeting_link = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    interviewer_name = Column(String(120), nullable=True)

    # Management
    recruiter_notes = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)  # freeform feedback after completion
    outcome = Column(String(32), nullable=True)  # pass | fail | on_hold
    completed_at = Column(DateTime(timezone=True), nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    application = relationship("Application", back_populates="interviews")
