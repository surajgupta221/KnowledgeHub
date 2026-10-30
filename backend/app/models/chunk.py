from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Chunk(Base):
    """
    Chunks of documents for RAG pipeline.
    
    Links to Document, stores text content + embedding vector.
    Multiple chunks per document, searchable by pgvector similarity.
    """
    __tablename__ = 'chunks'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)  # Order within document
    text = Column(Text, nullable=False)
    embedding = Column(String, nullable=True)  # pgvector embedding (1536-dim)
    tokens = Column(Integer, nullable=True)  # Token count for cost tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    document = relationship('Document', back_populates='chunks')

    # Index for efficient retrieval
    __table_args__ = (
        Index('ix_chunks_document_sequence', 'document_id', 'sequence'),
    )
