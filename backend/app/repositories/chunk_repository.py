"""Repository for Chunk model - encapsulates DB access."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.chunk import Chunk


class ChunkRepository:
    """Repository for chunk persistence and retrieval."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chunk(
        self,
        document_id: int,
        sequence: int,
        text: str,
        tokens: int | None = None,
        embedding: list[float] | None = None,
    ) -> Chunk:
        """
        Create and store a chunk.

        Args:
            document_id: Document ID
            sequence: Chunk sequence number (0, 1, 2, ...)
            text: Chunk text
            tokens: Optional token count
            embedding: Optional embedding vector

        Returns:
            Created Chunk model
        """
        chunk = Chunk(
            document_id=document_id,
            sequence=sequence,
            text=text,
            tokens=tokens,
            embedding=json.dumps(embedding) if embedding else None,
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def get_chunk(self, chunk_id: int) -> Chunk | None:
        """Retrieve chunk by ID."""
        result = await self.session.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def get_chunks_for_document(self, document_id: int) -> list[Chunk]:
        """Retrieve all chunks for a document."""
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.sequence)
        )
        return result.scalars().all()

    async def delete_chunks_for_document(self, document_id: int) -> int:
        """Delete all chunks for a document (e.g., before re-chunking)."""
        result = await self.session.execute(
            select(Chunk).where(Chunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        for chunk in chunks:
            await self.session.delete(chunk)
        await self.session.flush()
        return len(chunks)
