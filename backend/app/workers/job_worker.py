"""Background job worker for processing queued tasks."""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.services.job_service import JobService
from app.services.llm_client import LlmClient

logger = logging.getLogger(__name__)


class JobWorker:
    """Async worker that processes jobs from queue."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.llm_client = LlmClient(settings.llm_base_url, settings.llm_api_key)

    async def enqueue_job(self, job_id: int) -> None:
        """Add job to processing queue."""
        await self.queue.put(job_id)

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
        async for token in self.llm_client.stream_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=200
        ):
            summary_tokens.append(token)

        return ''.join(summary_tokens)

    async def stop(self) -> None:
        """Stop worker gracefully."""
        self.running = False
        await self.queue.join()
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
    asyncio.create_task(worker.process_jobs())
    logger.info("Worker task created")


async def stop_worker() -> None:
    """Stop background worker task."""
    worker = get_worker()
    await worker.stop()
    logger.info("Worker task stopped")
