"""Job status polling endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.services.job_service import JobService
from app.schemas.job_schemas import JobStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """
    Get job status by ID.

    Returns current status, result (if completed), and error (if failed).
    Client polls this endpoint to track background job progress.
    """
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    # 404 (not 403) so job existence is not revealed across tenants
    if not job or job.user_id != current_user:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse.model_validate(job)
