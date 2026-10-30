"""Document request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class DocumentResponse(BaseModel):
    """Document response schema."""

    id: int
    title: str
    content: Optional[str] = None
    owner_id: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List of documents response."""

    documents: list[DocumentResponse]
    total: int = 0


class DocumentUploadRequest(BaseModel):
    """Upload document request."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DocumentSummaryResponse(BaseModel):
    """Document summary response."""

    doc_id: int
    summary: str
    style: Optional[str] = None
