"""Embedding service for RAG pipeline."""

import json
import logging
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.config import settings
from app.models.chunk import Chunk

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and storing embeddings for chunks."""

    def __init__(self, db: AsyncSession, base_url: str = ""):
        """
        Initialize embedding service.

        Args:
            db: Async SQLAlchemy session
            base_url: Mock LLM server URL for embeddings (or use settings)
        """
        self.db = db
        self.base_url = base_url or settings.mock_llm_url

    async def embed_chunks(
        self, document_id: int, chunks: list[Chunk]
    ) -> int:
        """
        Generate embeddings for chunks and store in database.

        Batches requests to /v1/embeddings endpoint. Each call generates
        embeddings for multiple texts.

        Args:
            document_id: Document ID (for logging)
            chunks: List of Chunk ORM objects (must already be in DB)

        Returns:
            Number of chunks successfully embedded

        Raises:
            Exception: On API errors or database errors
        """
        if not chunks:
            logger.info(
                "No chunks to embed",
                extra={"document_id": document_id},
            )
            return 0

        try:
            # Extract texts from chunks
            chunk_texts = [chunk.text for chunk in chunks]

            # Call embedding API
            embeddings_data = await self._get_embeddings(chunk_texts)

            if not embeddings_data or len(embeddings_data) != len(chunks):
                raise Exception(
                    f"Embedding API returned {len(embeddings_data) or 0} embeddings, "
                    f"expected {len(chunks)}"
                )

            # Store embeddings in database
            for chunk, embedding in zip(chunks, embeddings_data):
                # Store as JSON string (pgvector will handle parsing)
                chunk.embedding = json.dumps(embedding)

            self.db.add_all(chunks)
            await self.db.commit()

            logger.info(
                "Chunks embedded successfully",
                extra={
                    "document_id": document_id,
                    "chunk_count": len(chunks),
                    "embedding_dim": len(embeddings_data[0]) if embeddings_data else 0,
                },
            )

            return len(chunks)

        except Exception as e:
            logger.error(
                "Failed to embed chunks",
                extra={
                    "document_id": document_id,
                    "chunk_count": len(chunks),
                    "error": str(e),
                },
            )
            await self.db.rollback()
            raise

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Call /v1/embeddings endpoint to generate embeddings.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each is list of floats)

        Raises:
            Exception: On API errors
        """
        payload = {
            "model": "mock-embedding",
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json=payload,
                    headers={"Authorization": "Bearer ****"},
                )

                if response.status_code != 200:
                    raise Exception(
                        f"Embedding API error {response.status_code}: {response.text}"
                    )

                data = response.json()

                # Extract embeddings from response
                # Expected format: { "data": [{"embedding": [...]}, ...], ... }
                embeddings_list = data.get("data", [])

                if not embeddings_list:
                    raise Exception("No embeddings returned from API")

                # Sort by index to maintain order
                embeddings_list.sort(key=lambda x: x.get("index", 0))

                return [item["embedding"] for item in embeddings_list]

        except httpx.TimeoutException:
            logger.error("Embedding API timeout")
            raise Exception("Embedding API timeout")
        except Exception as e:
            logger.error(
                "Embedding API call failed",
                extra={"error": str(e)},
            )
            raise

    async def get_chunk_embedding(self, chunk_id: int) -> Optional[list[float]]:
        """
        Retrieve embedding for a specific chunk.

        Args:
            chunk_id: Chunk ID

        Returns:
            Embedding vector as list of floats, or None if not embedded

        Raises:
            Exception: On database errors
        """
        try:
            stmt = select(Chunk).where(Chunk.id == chunk_id)
            result = await self.db.execute(stmt)
            chunk = result.scalar_one_or_none()

            if not chunk:
                return None

            if not chunk.embedding:
                return None

            # Parse JSON embedding
            return json.loads(chunk.embedding)

        except Exception as e:
            logger.error(
                "Failed to retrieve chunk embedding",
                extra={"chunk_id": chunk_id, "error": str(e)},
            )
            raise
