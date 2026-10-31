"""ChatService._build_context must work with the real RetrievalService."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService


@pytest.mark.asyncio
async def test_build_context_returns_matching_chunk_text(
    db_session: AsyncSession,
) -> None:
    doc = Document(owner_id="user_a", filename="policy.txt", content="x")
    db_session.add(doc)
    await db_session.commit()
    db_session.add(
        Chunk(
            document_id=doc.id,
            sequence=0,
            text="Passwords must be rotated every 90 days.",
            embedding=json.dumps([1.0, 0.0, 0.0]),
        )
    )
    await db_session.commit()

    embedding_service = MagicMock()
    embedding_service._get_embeddings = AsyncMock(return_value=[[1.0, 0.0, 0.0]])
    service = ChatService(
        db_session,
        llm_client=MagicMock(),
        embedding_service=embedding_service,
        retrieval_service=RetrievalService(db_session),
    )

    context = await service._build_context([doc.id], "How often are passwords rotated?")

    assert "Passwords must be rotated every 90 days." in context
    assert "Error retrieving context" not in context
