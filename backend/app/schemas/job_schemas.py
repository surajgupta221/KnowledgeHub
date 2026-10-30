"""Job request/response schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class JobStatusResponse(BaseModel):
    """Job status response."""

    id: int
    document_id: int
    job_type: str
    status: str  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobCreateResponse(BaseModel):
    """Response when creating a job (202 Accepted)."""

    job_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
