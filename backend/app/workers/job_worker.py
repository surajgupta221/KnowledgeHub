"""Background job worker for processing queued tasks."""

import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.services.job_service import JobService
from app.services.llm_client import LlmClient
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.repositories.chunk_repository import ChunkRepository

logger = logging.getLogger(__name__)


class JobQueueFullError(Exception):
    """Raised when the bounded job queue cannot accept more work."""


class JobWorker:
    """Async worker that processes jobs from queue."""

    def __init__(self, llm_client: LlmClient | None = None):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=settings.job_queue_size)
        self.running = False
        self.llm_client = llm_client or LlmClient(
            settings.mock_llm_url,
            timeout=settings.llm_timeout_seconds,
            api_key=settings.llm_api_key,
        )
        # Limits simultaneous LLM calls so background jobs cannot starve chat
        self._llm_semaphore = asyncio.Semaphore(settings.job_max_concurrent_llm_calls)
        self._tasks: list[asyncio.Task] = []

    def is_full(self) -> bool:
        return self.queue.full()

    async def enqueue_job(self, job_id: int) -> None:
        """Add job to the queue without blocking; raise if full."""
        try:
            self.queue.put_nowait(job_id)
        except asyncio.QueueFull as exc:
            raise JobQueueFullError("Job queue is full") from exc

    async def process_jobs(self) -> None:
        """Main worker loop - processes jobs from queue."""
        self.running = True
        logger.info("Job worker started")

        try:
            while self.running:
                try:
                    # Wait for job with 1s timeout
                    job_id = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No jobs, continue waiting
                    continue

                try:
                    await self._process_job(job_id)
                except Exception as e:
                    logger.exception(f"Error processing job {job_id}: {e}")
                finally:
                    self.queue.task_done()

        except asyncio.CancelledError:
            logger.info("Job worker cancelled")
            self.running = False
            raise
        except Exception as e:
            logger.exception(f"Job worker crashed: {e}")
            self.running = False

    async def _process_job(self, job_id: int) -> None:
        """Process single job (create new session for DB access)."""
        async with await get_session() as session:
            job_service = JobService(session)

            # Get job with document
            result = await job_service.get_job_with_document(job_id)
            if not result:
                logger.error(f"Job {job_id} not found")
                return

            job, document = result

            try:
                # Mark as running
                await job_service.start_job(job_id)
                await job_service.commit()

                # Process based on job type
                if job.job_type == 'summary':
                    summary = await self._generate_summary(document.content)
                    await job_service.complete_job(job_id, summary)
                elif job.job_type == 'embed_chunks':
                    chunk_count = await self._embed_document_chunks(
                        session, document.id, document.content
                    )
                    result = json.dumps({"chunks_created": chunk_count})
                    await job_service.complete_job(job_id, result)
                else:
                    raise ValueError(f"Unknown job type: {job.job_type}")

                await job_service.commit()
                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                error_msg = str(e)
                await job_service.fail_job(job_id, error_msg, retry=True)
                await job_service.commit()
                logger.error(f"Job {job_id} failed: {error_msg}")

    async def _generate_summary(self, content: str) -> str:
        """Generate document summary using LLM."""
        prompt = f"Summarize this document in 3-5 sentences:\n\n{content[:2000]}"

        summary_tokens = []
        async with self._llm_semaphore:
            async for token in self.llm_client.stream_completion(
                [{"role": "user", "content": prompt}],
                max_tokens=200
            ):
                summary_tokens.append(token)

        return ''.join(summary_tokens)

    async def _embed_document_chunks(
        self, session: AsyncSession, document_id: int, content: str
    ) -> int:
        """
        Chunk document and generate embeddings.

        Steps:
        1. Split document into chunks using ChunkingService
        2. Generate embeddings using EmbeddingService
        3. Store chunks with embeddings in DB

        Args:
            session: DB session
            document_id: Document ID
            content: Document content

        Returns:
            Number of chunks created
        """

        # Step 1: Split into chunks
        chunking_service = ChunkingService()
        chunks = chunking_service.chunk_text(content, document_id)

        if not chunks:
            logger.warning(f"No chunks created for document {document_id}")
            return 0

        # Step 2: Persist chunks (replacing any left by a previous attempt)
        chunk_repo = ChunkRepository(session)
        await chunk_repo.delete_chunks_for_document(document_id)
        stored_chunks = [
            await chunk_repo.create_chunk(
                document_id=chunk_data["document_id"],
                sequence=chunk_data["sequence"],
                text=chunk_data["text"],
                tokens=chunk_data.get("token_estimate"),
            )
            for chunk_data in chunks
        ]

        # Step 3: Generate embeddings; EmbeddingService fills them in and commits
        embedding_service = EmbeddingService(session)
        embedded_count = await embedding_service.embed_chunks(
            document_id, stored_chunks
        )

        logger.info(f"Embedded document {document_id}: {embedded_count} chunks")
        return embedded_count

    async def stop(self) -> None:
        """Stop worker gracefully."""
        self.running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("Job worker stopped")


# Global worker instance
_worker: JobWorker | None = None


def get_worker() -> JobWorker:
    """Get or create global worker instance."""
    global _worker
    if _worker is None:
        _worker = JobWorker()
    return _worker


async def start_worker() -> None:
    """Start background worker task."""
    worker = get_worker()
    if not worker._tasks:
        worker._tasks = [
            asyncio.create_task(worker.process_jobs())
            for _ in range(settings.job_worker_count)
        ]
    logger.info("Worker tasks created")


async def stop_worker() -> None:
    """Stop background worker task."""
    worker = get_worker()
    await worker.stop()
    logger.info("Worker task stopped")
