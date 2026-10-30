"""Job service for background task management."""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job import Job
from app.models.document import Document


class JobService:
    """Manages job lifecycle and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_summary_job(self, document_id: int, user_id: str) -> Job:
        """Create a background summarization job."""
        job = Job(
            document_id=document_id,
            user_id=user_id,
            job_type='summary',
            status='pending',
            retry_count=0,
            max_retries=3,
        )
        self.session.add(job)
        await self.session.flush()  # Get ID without commit
        return job

    async def get_job(self, job_id: int) -> Job | None:
        """Retrieve job by ID."""
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_job_with_document(self, job_id: int) -> tuple[Job, Document] | None:
        """Retrieve job with its document."""
        result = await self.session.execute(
            select(Job, Document)
            .join(Document)
            .where(Job.id == job_id)
        )
        row = result.first()
        return row if row else None

    async def start_job(self, job_id: int) -> None:
        """Mark job as running."""
        job = await self.get_job(job_id)
        if job:
            job.status = 'running'
            job.started_at = datetime.utcnow()
            self.session.add(job)
            await self.session.flush()

    async def complete_job(self, job_id: int, result: str) -> None:
        """Mark job as completed with result."""
        job = await self.get_job(job_id)
        if job:
            job.status = 'completed'
            job.result = result
            job.completed_at = datetime.utcnow()
            self.session.add(job)
            await self.session.flush()

    async def fail_job(self, job_id: int, error: str, retry: bool = True) -> None:
        """Mark job as failed, optionally retry."""
        job = await self.get_job(job_id)
        if job:
            job.error = error
            job.retry_count += 1

            if job.retry_count < job.max_retries and retry:
                job.status = 'pending'
                job.started_at = None
            else:
                job.status = 'failed'
                job.completed_at = datetime.utcnow()

            self.session.add(job)
            await self.session.flush()

    async def commit(self) -> None:
        """Commit all pending changes."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback pending changes."""
        await self.session.rollback()
