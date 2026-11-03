"""Chat request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ChatStreamRequest(BaseModel):
    """Chat stream request."""

    question: str = Field(..., min_length=1, max_length=5000)
    document_ids: list[int] = Field(default_factory=list, min_length=0, max_length=100)

    class Config:
        from_attributes = True


class ChatStreamEvent(BaseModel):
    """SSE event for streaming chat."""

    event: str  # "token", "done", "error"
    data: Optional[str] = None  # token content or error message


class Citation(BaseModel):
    """A source chunk supporting an answer."""

    document_id: int
    chunk_id: int
    quote: str = Field(..., min_length=1, max_length=1000)


class RagAnswer(BaseModel):
    """Strict schema the LLM's JSON output must satisfy."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., min_length=1, max_length=10000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list, max_length=20)


class ChatMessage(BaseModel):
    """Chat message response."""

    id: int
    question: str
    answer: str
    user_id: str
    created_at: Optional[str] = None
