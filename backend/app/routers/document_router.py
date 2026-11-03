"""Document router (production quality - refactored from AI-written version)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.document_schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadRequest,
)
from app.services.document_service import DocumentService
from app.services.job_service import JobService
from app.workers.job_worker import get_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    request: DocumentUploadRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload a new document and queue embedding job.

    - User ID extracted from auth context (JWT/session)
    - Input validated by Pydantic schema
    - Returns response schema (never ORM model)
    - Queues background job to chunk and embed document
    - Logs operation with user_id and doc_id (no content)
    """
    try:
        service = DocumentService(db)
        doc = await service.create_document(
            filename=request.filename,
            content=request.content,
            owner_id=current_user_id,
        )

        # Queue embedding job (chunk + embed in background)
        try:
            job_service = JobService(db)
            job = await job_service.create_embed_chunks_job(
                document_id=doc.id,
                user_id=current_user_id,
            )
            await job_service.commit()

            # Enqueue job for background processing
            worker = get_worker()
            await worker.enqueue_job(job.id)

            logger.info(
                "Document uploaded and embedding job queued",
                extra={
                    "user_id": current_user_id,
                    "doc_id": doc.id,
                    "job_id": job.id,
                },
            )
        except Exception as e:
            # Log job queueing error but don't fail upload
            logger.error(
                "Failed to queue embedding job",
                extra={
                    "user_id": current_user_id,
                    "doc_id": doc.id,
                    "error": str(e),
                },
            )

        return DocumentResponse.from_orm(doc)
    except Exception as e:
        logger.error(
            "Failed to upload document",
            extra={"user_id": current_user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to upload document")


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    """
    List documents owned by the current user.

    - Paginated with limit (1-100, default 20) and offset
    - Filters by owner_id in SQL query (not in Python)
    - Returns response schema
    - Returns total count for pagination UI
    """
    try:
        service = DocumentService(db)
        docs, total = await service.list_documents_for_user(
            current_user_id=current_user_id,
            limit=limit,
            offset=offset,
        )
        logger.info(
            "Documents listed",
            extra={
                "user_id": current_user_id,
                "count": len(docs),
                "limit": limit,
                "offset": offset,
            },
        )
        return DocumentListResponse(
            items=[DocumentResponse.from_orm(d) for d in docs],
            total=total,
        )
    except Exception as e:
        logger.error(
            "Failed to list documents",
            extra={"user_id": current_user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Get a single document by ID.

    - Verifies current user owns the document
    - Returns 404 if not owned (hides existence)
    - Returns response schema
    """
    try:
        service = DocumentService(db)
        doc = await service.get_document(
            doc_id=doc_id,
            current_user_id=current_user_id,
        )
        if not doc:
            logger.warning(
                "Document not found or not owned",
                extra={"user_id": current_user_id, "doc_id": doc_id},
            )
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info(
            "Document retrieved",
            extra={"user_id": current_user_id, "doc_id": doc_id},
        )
        return DocumentResponse.from_orm(doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve document",
            extra={"user_id": current_user_id, "doc_id": doc_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


@router.post("/{doc_id}/summary", status_code=202)
async def request_document_summary(
    doc_id: int,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Request background summarization of a document.

    - Verifies current user owns the document
    - Creates a background job
    - Returns 202 Accepted with job_id in Location header
    - Client polls GET /api/jobs/{job_id} for status
    """
    try:
        service = DocumentService(db)
        job_id = await service.create_summary_job(doc_id, current_user_id)

        if not job_id:
            logger.warning(
                "Document not found for summary",
                extra={"user_id": current_user_id, "doc_id": doc_id},
            )
            raise HTTPException(status_code=404, detail="Document not found")

        # Enqueue job for background processing
        from app.workers.job_worker import JobQueueFullError, get_worker
        worker = get_worker()
        try:
            await worker.enqueue_job(job_id)
        except JobQueueFullError:
            raise HTTPException(
                status_code=429,
                detail="Server is busy, try again shortly",
                headers={"Retry-After": "5"},
            )

        logger.info(
            "Summary job created",
            extra={
                "user_id": current_user_id,
                "doc_id": doc_id,
                "job_id": job_id,
            },
        )

        return {"job_id": job_id, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create summary job",
            extra={
                "user_id": current_user_id,
                "doc_id": doc_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to create summary job")


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document.

    - Verifies current user owns the document
    - Returns 404 if not owned (hides existence)
    - Returns 204 No Content on success
    - Returns 404 if document doesn't exist
    """
    try:
        service = DocumentService(db)
        deleted = await service.delete_document(
            doc_id=doc_id,
            current_user_id=current_user_id,
        )
        if not deleted:
            logger.warning(
                "Document not found for deletion",
                extra={"user_id": current_user_id, "doc_id": doc_id},
            )
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info(
            "Document deleted",
            extra={"user_id": current_user_id, "doc_id": doc_id},
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete document",
            extra={"user_id": current_user_id, "doc_id": doc_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to delete document")
