from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from app.models.base import Base


class ChatMessage(Base):
    """
    Chat message history for persistence.
    
    Stores user questions and assistant answers.
    Linked to Document(s) for context.
    Enables conversation recall and analysis.
    """
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)  # Conversation session identifier
    user_id = Column(String(255), nullable=False, index=True)  # User who sent message
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    document_ids = Column(String(1000), nullable=True)  # Comma-separated doc IDs used
    tokens_used = Column(Integer, nullable=True)  # Token count for cost tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_chat_messages_session', 'session_id'),
        Index('ix_chat_messages_user_session', 'user_id', 'session_id'),
    )
