from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_title = Column(String(150), nullable=False)
    short_description = Column(String(255), nullable=True)
    job_link = Column(String(255), nullable=True)
    salary_range = Column(String(50), nullable=True)
    salary_currency = Column(String(5), nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    variable_min = Column(Integer, nullable=True)
    variable_max = Column(Integer, nullable=True)
    location = Column(String(100), nullable=True)
    job_description = Column(Text, nullable=True)
    additional_preferences = Column(Text, nullable=True)
    non_negotiables = Column(Text, nullable=True)  # JSON string list
    opportunity_type = Column(String(20), nullable=True)
    min_experience_years = Column(Integer, nullable=True)
    job_type = Column(String(20), nullable=True)
    job_site = Column(String(20), nullable=True)
    openings = Column(Integer, nullable=True)
    perks = Column(Text, nullable=True)  # JSON string of perks
    screening_availability = Column(String(255), nullable=True)
    screening_phone = Column(String(30), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)  # Job start date
    duration = Column(String(100), nullable=True)  # e.g., "6 months", "1 year", "Permanent"
    apply_by = Column(DateTime(timezone=True), nullable=True)  # Application deadline
    required_skills = Column(Text, nullable=True)  # JSON string list of required skills
    status = Column(String(20), nullable=False, default="active")
    draft_data = Column(Text, nullable=True)  # JSON string of full CreateJob form state
    draft_step = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="jobs")
    # Deleting a job should also remove dependent applications at ORM level.
    # (DB-level cascades may vary by engine; API also performs manual cleanup.)
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

