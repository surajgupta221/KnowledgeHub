"""Tests for retrieval service."""

import pytest
import json
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.retrieval_service import RetrievalService
from app.models.chunk import Chunk
from app.models.document import Document


class TestRetrievalCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_cosine_similarity_identical_vectors(self):
        """Test similarity of identical vectors."""
        service = RetrievalService(db=None)
        vec = [1.0, 0.0, 0.0]

        similarity = service._cosine_similarity(vec, vec)

        assert abs(similarity - 1.0) < 0.0001  # Should be 1.0

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test similarity of orthogonal (perpendicular) vectors."""
        service = RetrievalService(db=None)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = service._cosine_similarity(vec1, vec2)

        assert abs(similarity) < 0.0001  # Should be 0.0

    def test_cosine_similarity_opposite_vectors(self):
        """Test similarity of opposite vectors."""
        service = RetrievalService(db=None)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        similarity = service._cosine_similarity(vec1, vec2)

        assert abs(similarity - (-1.0)) < 0.0001  # Should be -1.0

    def test_cosine_similarity_general_case(self):
        """Test similarity in general case."""
        service = RetrievalService(db=None)
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]

        # Manually calculate: (1*4 + 2*5 + 3*6) / (sqrt(1+4+9) * sqrt(16+25+36))
        # = (4+10+18) / (sqrt(14) * sqrt(77))
        # = 32 / (3.742 * 8.775) = 32 / 32.864 ≈ 0.974
        similarity = service._cosine_similarity(vec1, vec2)

        assert 0.97 < similarity < 0.98

    def test_cosine_similarity_zero_vector(self):
        """Test similarity with zero vector."""
        service = RetrievalService(db=None)
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = service._cosine_similarity(vec1, vec2)

        assert similarity == 0.0

    def test_cosine_similarity_dimension_mismatch(self):
        """Test error on mismatched dimensions."""
        service = RetrievalService(db=None)
        vec1 = [1.0, 2.0]
        vec2 = [3.0, 4.0, 5.0]

        with pytest.raises(ValueError):
            service._cosine_similarity(vec1, vec2)


class TestRetrievalFormatting:
    """Test chunk formatting for context."""

    def test_format_retrieved_chunks_empty(self):
        """Test formatting with no chunks."""
        service = RetrievalService(db=None)
        formatted = service._format_retrieved_chunks_sync([])

        assert "(No relevant chunks found)" in formatted

    def test_format_retrieved_chunks_single(self):
        """Test formatting with single chunk."""
        service = RetrievalService(db=None)
        chunks = [
            {
                "id": 1,
                "document_id": 10,
                "text": "This is a test chunk.",
                "similarity": 0.92,
            }
        ]

        formatted = service._format_retrieved_chunks_sync(chunks)

        assert "[1]" in formatted
        assert "Document ID: 10" in formatted
        assert "0.92" in formatted
        assert "This is a test chunk." in formatted

    def test_format_retrieved_chunks_multiple(self):
        """Test formatting with multiple chunks from different docs."""
        service = RetrievalService(db=None)
        chunks = [
            {
                "id": 1,
                "document_id": 10,
                "text": "First chunk text.",
                "similarity": 0.95,
            },
            {
                "id": 2,
                "document_id": 10,
                "text": "Second chunk text.",
                "similarity": 0.87,
            },
            {
                "id": 3,
                "document_id": 20,
                "text": "Third chunk text.",
                "similarity": 0.85,
            },
        ]

        formatted = service._format_retrieved_chunks_sync(chunks)

        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "[3]" in formatted
        assert "Retrieved 3 most relevant chunks" in formatted
        assert "2 documents" in formatted


class TestRetrievalIntegration:
    """Integration tests for retrieval service."""

    @pytest.mark.asyncio
    async def test_retrieve_relevant_chunks(self, db_session: AsyncSession):
        """Test retrieving relevant chunks from database."""
        # Create test documents and chunks
        doc1 = Document(
            owner_id="user_a",
            filename="doc1.txt",
            content="Test content",
            doc_metadata=None,
        )
        doc2 = Document(
            owner_id="user_a",
            filename="doc2.txt",
            content="Other content",
            doc_metadata=None,
        )
        db_session.add_all([doc1, doc2])
        await db_session.commit()

        # Create chunks with embeddings
        chunks = [
            # Similar to query (high similarity)
            Chunk(
                document_id=doc1.id,
                sequence=0,
                text="Information about policy and benefits.",
                embedding=json.dumps([0.8, 0.2, 0.0]),  # Similar to query
            ),
            # Less similar
            Chunk(
                document_id=doc1.id,
                sequence=1,
                text="Technical details about systems.",
                embedding=json.dumps([0.1, 0.2, 0.8]),  # Different from query
            ),
            # Should be excluded (not in document_ids)
            Chunk(
                document_id=doc2.id,
                sequence=0,
                text="Other document content.",
                embedding=json.dumps([0.9, 0.1, 0.0]),
            ),
        ]
        db_session.add_all(chunks)
        await db_session.commit()

        # Query embedding similar to first chunk
        query_embedding = [0.75, 0.25, 0.0]

        service = RetrievalService(db_session, top_k=5, similarity_threshold=0.5)
        results = await service.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            document_ids=[doc1.id],  # Only search doc1
        )

        # Should retrieve chunk from doc1, not doc2
        assert len(results) > 0
        assert all(r["document_id"] == doc1.id for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_respects_threshold(self, db_session: AsyncSession):
        """Test that low-similarity chunks are filtered."""
        doc = Document(
            owner_id="user_a",
            filename="test.txt",
            content="Test",
            doc_metadata=None,
        )
        db_session.add(doc)
        await db_session.commit()

        chunk = Chunk(
            document_id=doc.id,
            sequence=0,
            text="Unrelated content here.",
            embedding=json.dumps([0.0, 0.0, 1.0]),  # Orthogonal to query
        )
        db_session.add(chunk)
        await db_session.commit()

        query_embedding = [1.0, 0.0, 0.0]

        service = RetrievalService(db_session, similarity_threshold=0.7)
        results = await service.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            document_ids=[doc.id],
        )

        # Should be empty (similarity near 0, threshold 0.7)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_respects_top_k(self, db_session: AsyncSession):
        """Test that only top-K results are returned."""
        doc = Document(
            owner_id="user_a",
            filename="test.txt",
            content="Test",
            doc_metadata=None,
        )
        db_session.add(doc)
        await db_session.commit()

        # Create 10 chunks with varying similarities
        chunks = [
            Chunk(
                document_id=doc.id,
                sequence=i,
                text=f"Chunk {i} content.",
                embedding=json.dumps([1.0 - (i * 0.05), 0.0, 0.0]),
            )
            for i in range(10)
        ]
        db_session.add_all(chunks)
        await db_session.commit()

        query_embedding = [1.0, 0.0, 0.0]

        service = RetrievalService(db_session, top_k=3, similarity_threshold=0.0)
        results = await service.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            document_ids=[doc.id],
        )

        # Should return only top 3
        assert len(results) == 3

        # Should be sorted by similarity descending
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]

    @pytest.mark.asyncio
    async def test_retrieve_no_embedded_chunks(self, db_session: AsyncSession):
        """Test retrieval when no chunks have embeddings."""
        doc = Document(
            owner_id="user_a",
            filename="test.txt",
            content="Test",
            doc_metadata=None,
        )
        db_session.add(doc)
        await db_session.commit()

        chunk = Chunk(
            document_id=doc.id,
            sequence=0,
            text="No embedding for this chunk.",
            embedding=None,  # No embedding
        )
        db_session.add(chunk)
        await db_session.commit()

        query_embedding = [1.0, 0.0, 0.0]

        service = RetrievalService(db_session)
        results = await service.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            document_ids=[doc.id],
        )

        # Should return empty (no embedded chunks)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_empty_document_list(self, db_session: AsyncSession):
        """Test retrieval with empty document list."""
        service = RetrievalService(db_session)
        results = await service.retrieve_relevant_chunks(
            query_embedding=[1.0, 0.0, 0.0],
            document_ids=[],
        )

        assert len(results) == 0
