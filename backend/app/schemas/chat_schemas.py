"""Chat request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatStreamRequest(BaseModel):
    """Chat stream request."""

    question: str = Field(..., min_length=1, max_length=5000)
    document_ids: list[int] = Field(default_factory=list, min_items=0, max_items=100)

    class Config:
        from_attributes = True


class ChatStreamEvent(BaseModel):
    """SSE event for streaming chat."""

    event: str  # "token", "done", "error"
    data: Optional[str] = None  # token content or error message


class ChatMessage(BaseModel):
    """Chat message response."""

    id: int
    question: str
    answer: str
    user_id: str
    created_at: Optional[str] = None
