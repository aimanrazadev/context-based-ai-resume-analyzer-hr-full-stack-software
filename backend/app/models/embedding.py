from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.sql import func

from ..database import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(20), nullable=False)  # job | resume
    entity_id = Column(Integer, nullable=False)
    model = Column(String(120), nullable=False)
    dim = Column(Integer, nullable=False, default=0)
    text_hash = Column(String(64), nullable=False)
    vector_json = Column(Text, nullable=False)  # JSON array of floats
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "model", "text_hash", name="uq_embeddings_entity_model_hash"),
        Index("ix_embeddings_lookup", "entity_type", "entity_id", "model"),
    )

