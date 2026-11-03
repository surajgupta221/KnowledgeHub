from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Job(Base):
    """
    Background job for long-running tasks (e.g., document summarization).
    
    Tracks job status, result, and error messages.
    Linked to Document for context.
    """
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(255), nullable=False)  # User who created this job
    job_type = Column(String(50), nullable=False)  # "summary", "embed_chunks", etc.
    status = Column(String(20), default='pending', nullable=False)  # pending, running, completed, failed
    result = Column(Text, nullable=True)  # JSON result
    error = Column(Text, nullable=True)  # Error message if failed
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationship
    document = relationship('Document', back_populates='jobs')
