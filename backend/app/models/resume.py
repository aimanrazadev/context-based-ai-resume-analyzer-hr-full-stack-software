from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    # Relative path under UPLOAD_DIR (portable across machines)
    file_path = Column(String(500), nullable=False)
    # Metadata (nullable to allow older DB rows created before this feature)
    stored_filename = Column(String(255), nullable=True)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    extracted_text = Column(Text, nullable=True)
    # Module 7: structured data extracted from extracted_text (JSON string)
    structured_json = Column(Text, nullable=True)
    # Schema version for structured_json (allows evolving format)
    structured_version = Column(Integer, nullable=False, default=1)
    # Module 8: AI-generated structured data (kept separate from deterministic structured_json)
    ai_structured_json = Column(Text, nullable=True)
    ai_structured_version = Column(Integer, nullable=False, default=1)
    ai_model = Column(String(120), nullable=True)
    ai_generated_at = Column(DateTime(timezone=True), nullable=True)
    ai_warnings = Column(Text, nullable=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", back_populates="resumes")

