"""Tests for background job worker, focusing on embedding pipeline."""

import json
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.job_service import JobService
from app.workers.job_worker import JobWorker
from app.repositories.chunk_repository import ChunkRepository


@pytest.mark.asyncio
class TestEmbedChunksJob:
    """Test embedding pipeline via background job."""

    async def test_create_embed_chunks_job(self, db_session: AsyncSession):
        """Test creating an embedding job."""
        job_service = JobService(db_session)

        job = await job_service.create_embed_chunks_job(
            document_id=1, user_id="user123"
        )
        await db_session.flush()

        assert job.id is not None
        assert job.document_id == 1
        assert job.user_id == "user123"
        assert job.job_type == "embed_chunks"
        assert job.status == "pending"
        assert job.retry_count == 0
        assert job.max_retries == 3

    async def test_embed_chunks_job_processing(self, db_session: AsyncSession):
        """Test that embed chunks job creates correct data structures."""
        # This test focuses on job creation and status management
        # Full integration testing would require Docker database
        doc = Document(
            id=1,
            filename="test.txt",
            content="First sentence. Second sentence. Third sentence.",
            owner_id="user123",
        )
        db_session.add(doc)
        await db_session.flush()

        job_service = JobService(db_session)
        job = await job_service.create_embed_chunks_job(
            document_id=doc.id, user_id="user123"
        )
        await db_session.commit()

        # Verify job created correctly
        assert job.id is not None
        assert job.job_type == "embed_chunks"
        assert job.status == "pending"

        # Verify job can be retrieved
        retrieved_job = await job_service.get_job(job.id)
        assert retrieved_job.document_id == doc.id

    async def test_embed_chunks_stores_metadata(self, db_session: AsyncSession):
        """Test that chunks can be stored with proper metadata."""
        repo = ChunkRepository(db_session)

        # Create test chunks
        for i in range(2):
            chunk = await repo.create_chunk(
                document_id=2,
                sequence=i,
                text=f"Test chunk {i}",
                tokens=50,
                embedding=[0.1, 0.2, 0.3],
            )
            assert chunk.id is not None
            assert chunk.sequence == i

        # Retrieve chunks
        chunks = await repo.get_chunks_for_document(2)
        assert len(chunks) == 2

        # Verify metadata
        for i, chunk in enumerate(chunks):
            assert chunk.document_id == 2
            assert chunk.sequence == i
            assert chunk.tokens == 50
            assert chunk.text == f"Test chunk {i}"

    async def test_embed_chunks_job_with_empty_document(self, db_session: AsyncSession):
        """Test creating embedding job for empty document."""
        doc = Document(
            id=3,
            filename="empty.txt",
            content="",
            owner_id="user789",
        )
        db_session.add(doc)
        await db_session.flush()

        job_service = JobService(db_session)
        job = await job_service.create_embed_chunks_job(
            document_id=doc.id, user_id="user789"
        )
        await db_session.commit()

        # Job creation should succeed even for empty doc
        assert job.id is not None
        assert job.document_id == doc.id

    async def test_embed_chunks_job_retry_on_failure(self, db_session: AsyncSession):
        """Test that failed jobs can be retried."""
        doc = Document(
            id=4,
            filename="retry_test.txt",
            content="Test content for retry.",
            owner_id="user123",
        )
        db_session.add(doc)
        await db_session.flush()

        job_service = JobService(db_session)
        job = await job_service.create_embed_chunks_job(
            document_id=doc.id, user_id="user123"
        )
        await db_session.commit()

        # Mark job as failed with retry
        await job_service.fail_job(job.id, "Network error", retry=True)
        await db_session.commit()

        # Verify job is retryable
        failed_job = await job_service.get_job(job.id)
        assert failed_job.status == "pending"
        assert failed_job.retry_count == 1
        assert failed_job.max_retries == 3

    async def test_embed_chunks_job_max_retries_exceeded(
        self, db_session: AsyncSession
    ):
        """Test that job fails permanently after max retries."""
        doc = Document(
            id=5,
            filename="max_retries_test.txt",
            content="Test content.",
            owner_id="user123",
        )
        db_session.add(doc)
        await db_session.flush()

        job_service = JobService(db_session)
        job = await job_service.create_embed_chunks_job(
            document_id=doc.id, user_id="user123"
        )
        job.max_retries = 2
        await db_session.commit()

        # Fail 3 times (exceeds max_retries=2)
        await job_service.fail_job(job.id, "Error 1", retry=True)
        await job_service.fail_job(job.id, "Error 2", retry=True)
        await job_service.fail_job(job.id, "Error 3", retry=True)
        await db_session.commit()

        # Verify job is now failed (not retryable)
        failed_job = await job_service.get_job(job.id)
        assert failed_job.status == "failed"
        assert failed_job.retry_count == 3
        assert failed_job.completed_at is not None

    async def test_chunk_repository_create_chunk(self, db_session: AsyncSession):
        """Test ChunkRepository.create_chunk()."""
        repo = ChunkRepository(db_session)

        embedding = [0.1, 0.2, 0.3]
        chunk = await repo.create_chunk(
            document_id=10,
            sequence=0,
            text="Test chunk text",
            tokens=42,
            embedding=embedding,
        )
        await db_session.flush()

        assert chunk.id is not None
        assert chunk.document_id == 10
        assert chunk.sequence == 0
        assert chunk.text == "Test chunk text"
        assert chunk.tokens == 42
        assert json.loads(chunk.embedding) == embedding

    async def test_chunk_repository_get_chunks_for_document(
        self, db_session: AsyncSession
    ):
        """Test ChunkRepository.get_chunks_for_document()."""
        repo = ChunkRepository(db_session)

        # Create 3 chunks
        for i in range(3):
            await repo.create_chunk(
                document_id=20,
                sequence=i,
                text=f"Chunk {i}",
                tokens=10,
                embedding=[0.1 * (i + 1)],
            )
        await db_session.flush()

        # Retrieve chunks
        chunks = await repo.get_chunks_for_document(20)
        assert len(chunks) == 3

        # Verify order
        for i, chunk in enumerate(chunks):
            assert chunk.sequence == i
            assert chunk.text == f"Chunk {i}"

    async def test_chunk_repository_delete_chunks(self, db_session: AsyncSession):
        """Test ChunkRepository.delete_chunks_for_document()."""
        repo = ChunkRepository(db_session)

        # Create 2 chunks
        for i in range(2):
            await repo.create_chunk(
                document_id=30,
                sequence=i,
                text=f"Chunk {i}",
                tokens=10,
            )
        await db_session.flush()

        # Delete chunks
        deleted_count = await repo.delete_chunks_for_document(30)
        await db_session.flush()

        assert deleted_count == 2

        # Verify deletion
        remaining = await repo.get_chunks_for_document(30)
        assert len(remaining) == 0
