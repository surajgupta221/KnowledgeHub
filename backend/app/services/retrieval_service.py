"""Retrieval service for RAG pipeline with pgvector similarity search."""

import json
import logging
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.chunk import Chunk

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant chunks via vector similarity search."""

    # Retrieval configuration
    TOP_K = 5  # Number of chunks to retrieve
    SIMILARITY_THRESHOLD = 0.7  # Minimum cosine similarity (0.0 to 1.0)

    def __init__(
        self,
        db: AsyncSession,
        top_k: int = TOP_K,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ):
        """
        Initialize retrieval service.

        Args:
            db: Async SQLAlchemy session
            top_k: Number of top chunks to retrieve
            similarity_threshold: Minimum similarity score for retrieval
        """
        self.db = db
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    async def retrieve_relevant_chunks(
        self,
        query_embedding: list[float],
        document_ids: list[int],
    ) -> list[dict]:
        """
        Retrieve top-K most similar chunks from specified documents.

        Uses cosine similarity for ranking. Filters by document ownership.

        Args:
            query_embedding: Query embedding vector (1536-dim for mock LLM)
            document_ids: Document IDs to search within

        Returns:
            List of chunk dicts: {
                'id': int,
                'document_id': int,
                'text': str,
                'similarity': float,
            }
            Sorted by similarity descending.

        Raises:
            Exception: On database or computation errors
        """
        if not document_ids or not query_embedding:
            logger.warning(
                "No documents or query embedding provided",
                extra={
                    "doc_count": len(document_ids) if document_ids else 0,
                    "embedding_dim": len(query_embedding) if query_embedding else 0,
                },
            )
            return []

        try:
            if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
                return await self._retrieve_pgvector(query_embedding, document_ids)

            # Fetch all chunks from specified documents (with embeddings)
            stmt = (
                select(Chunk)
                .where(Chunk.document_id.in_(document_ids))
                .where(Chunk.embedding.isnot(None))
                .options(selectinload(Chunk.document))
            )
            result = await self.db.execute(stmt)
            chunks = result.scalars().all()

            if not chunks:
                logger.info(
                    "No embedded chunks found",
                    extra={"document_ids": document_ids},
                )
                return []

            # Calculate similarity for each chunk
            similarities = []
            for chunk in chunks:
                try:
                    chunk_embedding = json.loads(chunk.embedding)
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)

                    if similarity >= self.similarity_threshold:
                        similarities.append({
                            "id": chunk.id,
                            "document_id": chunk.document_id,
                            "text": chunk.text,
                            "similarity": similarity,
                        })
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Failed to parse chunk embedding",
                        extra={"chunk_id": chunk.id, "error": str(e)},
                    )
                    continue

            # Sort by similarity descending and return top-K
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            result_chunks = similarities[: self.top_k]

            logger.info(
                "Retrieved relevant chunks",
                extra={
                    "query_docs": len(document_ids),
                    "candidates": len(chunks),
                    "above_threshold": len(similarities),
                    "returned": len(result_chunks),
                },
            )

            return result_chunks

        except Exception as e:
            logger.error(
                "Failed to retrieve chunks",
                extra={
                    "document_ids": document_ids,
                    "error": str(e),
                },
            )
            raise

    async def _retrieve_pgvector(
        self, query_embedding: list[float], document_ids: list[int]
    ) -> list[dict]:
        """Rank chunks inside Postgres using pgvector cosine distance (<=>)."""
        stmt = text(
            "SELECT id, document_id, text, "
            "1 - (CAST(embedding AS vector) <=> CAST(:q AS vector)) AS similarity "
            "FROM chunks "
            "WHERE document_id = ANY(:ids) AND embedding IS NOT NULL "
            "AND 1 - (CAST(embedding AS vector) <=> CAST(:q AS vector)) >= :thr "
            "ORDER BY similarity DESC LIMIT :k"
        )
        result = await self.db.execute(
            stmt,
            {
                "q": json.dumps(query_embedding),
                "ids": list(document_ids),
                "thr": self.similarity_threshold,
                "k": self.top_k,
            },
        )
        return [
            {
                "id": r.id,
                "document_id": r.document_id,
                "text": r.text,
                "similarity": float(r.similarity),
            }
            for r in result
        ]

    def _cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> float:
        """
        Calculate cosine similarity between two vectors.

        Formula: cos(θ) = (A · B) / (||A|| * ||B||)

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not vec1 or not vec2:
            return 0.0

        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vector dimensions must match: {len(vec1)} vs {len(vec2)}"
            )

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        # Cosine similarity
        return dot_product / (mag1 * mag2)

    def _format_retrieved_chunks_sync(
        self, chunks: list[dict]
    ) -> str:
        """
        Format retrieved chunks into a readable context string for LLM.

        Each chunk is delimited with metadata for citations.

        Args:
            chunks: List of chunk dicts from retrieve_relevant_chunks()

        Returns:
            Formatted context string
        """
        if not chunks:
            return "(No relevant chunks found)"

        # Build context with citations
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            # Format: [1] (Doc X, similarity 0.85) Chunk text...
            citation = (
                f"[{i}] (Document ID: {chunk['document_id']}, "
                f"similarity: {chunk['similarity']:.2f})"
            )
            context_parts.append(f"{citation}\n{chunk['text']}")

        context = "\n\n".join(context_parts)

        # Add retrieval note
        footer = (
            f"\n\nRetrieved {len(chunks)} most relevant chunks from "
            f"{len(set(c['document_id'] for c in chunks))} documents."
        )

        return context + footer

    async def format_retrieved_chunks(
        self, chunks: list[dict]
    ) -> str:
        """Async wrapper around sync formatting."""
        return self._format_retrieved_chunks_sync(chunks)
