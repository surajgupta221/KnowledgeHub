"""Tests for background job queue."""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_service import JobService
from app.models.job import Job


@pytest.mark.asyncio
async def test_create_summary_job(db_session: AsyncSession) -> None:
    """Test creating a summary job."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(
        document_id=1,
        user_id="user_a"
    )

    assert job.document_id == 1
    assert job.user_id == "user_a"
    assert job.job_type == "summary"
    assert job.status == "pending"
    assert job.retry_count == 0
    assert job.max_retries == 3


@pytest.mark.asyncio
async def test_get_job(db_session: AsyncSession) -> None:
    """Test retrieving a job."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(
        document_id=1,
        user_id="user_a"
    )
    await job_service.commit()

    # Retrieve it
    retrieved = await job_service.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.status == "pending"


@pytest.mark.asyncio
async def test_start_job(db_session: AsyncSession) -> None:
    """Test marking job as running."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(1, "user_a")
    await job_service.commit()

    await job_service.start_job(job.id)
    await job_service.commit()

    job = await job_service.get_job(job.id)
    assert job.status == "running"
    assert job.started_at is not None


@pytest.mark.asyncio
async def test_complete_job(db_session: AsyncSession) -> None:
    """Test marking job as completed."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(1, "user_a")
    await job_service.commit()

    result = "This is a summary."
    await job_service.complete_job(job.id, result)
    await job_service.commit()

    job = await job_service.get_job(job.id)
    assert job.status == "completed"
    assert job.result == result
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_fail_job_with_retry(db_session: AsyncSession) -> None:
    """Test marking job as failed with retry."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(1, "user_a")
    await job_service.commit()

    await job_service.fail_job(job.id, "Network error", retry=True)
    await job_service.commit()

    job = await job_service.get_job(job.id)
    assert job.status == "pending"  # Retry sets back to pending
    assert job.retry_count == 1
    assert job.error == "Network error"


@pytest.mark.asyncio
async def test_fail_job_no_retry(db_session: AsyncSession) -> None:
    """Test marking job as failed without retry."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(1, "user_a")

    # Fail without retry
    await job_service.fail_job(job.id, "Network error", retry=False)
    await db_session.commit()

    job = await job_service.get_job(job.id)
    assert job.status == "failed"
    assert job.retry_count == 1
    assert job.error == "Network error"


@pytest.mark.asyncio
async def test_fail_job_with_retry(db_session: AsyncSession) -> None:
    """Test marking job as failed with retry on non-max."""
    job_service = JobService(db_session)
    job = await job_service.create_summary_job(1, "user_a")
    # Default max_retries is 3, so first 3 failures should retry

    # First failure (will retry)
    await job_service.fail_job(job.id, "Error 1", retry=True)
    await db_session.commit()

    job = await job_service.get_job(job.id)
    assert job.status == "pending"
    assert job.retry_count == 1
    assert job.error == "Error 1"


@pytest.mark.asyncio
async def test_job_status_progression(db_session: AsyncSession) -> None:
    """Test complete job status progression."""
    job_service = JobService(db_session)

    # Create job (pending)
    job = await job_service.create_summary_job(1, "user_a")
    await job_service.commit()
    assert (await job_service.get_job(job.id)).status == "pending"

    # Start job (running)
    await job_service.start_job(job.id)
    await job_service.commit()
    assert (await job_service.get_job(job.id)).status == "running"

    # Complete job (completed)
    await job_service.complete_job(job.id, "Summary text")
    await job_service.commit()
    job = await job_service.get_job(job.id)
    assert job.status == "completed"
    assert job.result == "Summary text"
    assert job.started_at is not None
    assert job.completed_at is not None
