"""Document request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    """Document response schema."""

    id: int
    filename: str
    owner_id: str
    content: Optional[str] = None
    metadata: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List of documents response."""

    items: list[DocumentResponse]
    total: int = 0


class DocumentUploadRequest(BaseModel):
    """Upload document request."""

    filename: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DocumentSummaryResponse(BaseModel):
    """Document summary response."""

    doc_id: int
    summary: str

