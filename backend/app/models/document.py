"""Document ORM model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class Document(Base):
    """Document ORM model (never exported from service layer)."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks = relationship('Chunk', back_populates='document', cascade='all, delete-orphan')
    jobs = relationship('Job', back_populates='document', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        Index('ix_documents_owner', 'owner_id'),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, owner_id={self.owner_id}, filename={self.filename})>"

