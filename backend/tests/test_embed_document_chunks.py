"""Integration test: worker chunk -> embed -> store pipeline with real services."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.workers.job_worker import JobWorker

SHORT_POLICY = (
    "Passwords must be rotated every 90 days. MFA is mandatory for all employees."
)


async def _create_document(session: AsyncSession, content: str) -> Document:
    doc = Document(owner_id="user_a", filename="policy.txt", content=content)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def _stored_chunks(session: AsyncSession, document_id: int) -> list[Chunk]:
    result = await session.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.sequence)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_embed_document_chunks_stores_chunks_with_embeddings(
    db_session: AsyncSession,
) -> None:
    doc = await _create_document(db_session, SHORT_POLICY)
    worker = JobWorker()

    with patch(
        "app.services.embedding_service.EmbeddingService._get_embeddings",
        new=AsyncMock(return_value=[[0.1, 0.2, 0.3]]),
    ):
        count = await worker._embed_document_chunks(db_session, doc.id, doc.content)

    assert count == 1
    chunks = await _stored_chunks(db_session, doc.id)
    assert len(chunks) == 1
    assert "MFA is mandatory" in chunks[0].text
    assert json.loads(chunks[0].embedding) == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_document_chunks_is_idempotent_on_retry(
    db_session: AsyncSession,
) -> None:
    doc = await _create_document(db_session, SHORT_POLICY)
    worker = JobWorker()

    with patch(
        "app.services.embedding_service.EmbeddingService._get_embeddings",
        new=AsyncMock(return_value=[[0.1, 0.2, 0.3]]),
    ):
        await worker._embed_document_chunks(db_session, doc.id, doc.content)
        await worker._embed_document_chunks(db_session, doc.id, doc.content)

    assert len(await _stored_chunks(db_session, doc.id)) == 1


@pytest.mark.asyncio
async def test_embed_document_chunks_returns_zero_for_blank_content(
    db_session: AsyncSession,
) -> None:
    doc = await _create_document(db_session, "   ")
    worker = JobWorker()

    count = await worker._embed_document_chunks(db_session, doc.id, doc.content)

    assert count == 0
    assert await _stored_chunks(db_session, doc.id) == []
