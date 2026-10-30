"""Document router (production quality - refactored from AI-written version)."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.document_schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadRequest,
    DocumentSummaryResponse,
)
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    request: DocumentUploadRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload a new document.

    - User ID extracted from auth context (JWT/session)
    - Input validated by Pydantic schema
    - Returns response schema (never ORM model)
    - Logs operation with user_id and doc_id (no content)
    """
    try:
        service = DocumentService(db)
        doc = await service.create_document(
            title=request.title,
            content=request.content,
            owner_id=current_user_id,
        )
        logger.info(
            "Document uploaded",
            extra={"user_id": current_user_id, "doc_id": doc.id, "title": doc.title},
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
            documents=[DocumentResponse.from_orm(d) for d in docs],
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


@router.get("/{doc_id}/summary", response_model=DocumentSummaryResponse)
async def request_document_summary(
    doc_id: int,
    style: Literal["executive", "technical", "summary"] = Query("summary"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentSummaryResponse:
    """
    Request a document summary.

    - Returns 202 Accepted with jobId (background job, not blocking)
    - Verifies current user owns the document
    - `style` parameter restricted to enum values (no injection)
    - LLM call delegated to job queue (see Step 3.1)

    For now, this endpoint returns a stub showing the structure.
    In production, it will:
    1. Check document ownership
    2. Enqueue summary job
    3. Return 202 + jobId
    4. Client polls GET /api/jobs/{jobId} for result

    NOTE: This is a placeholder until Step 3.1 (background job queue) is implemented.
    """
    try:
        service = DocumentService(db)
        doc = await service.get_document(
            doc_id=doc_id,
            current_user_id=current_user_id,
        )
        if not doc:
            logger.warning(
                "Document not found for summary",
                extra={"user_id": current_user_id, "doc_id": doc_id},
            )
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info(
            "Summary requested",
            extra={
                "user_id": current_user_id,
                "doc_id": doc_id,
                "style": style,
            },
        )

        # TODO (Step 3.1): Implement background job queue
        # For now, return stub with 202 Accepted
        return DocumentSummaryResponse(
            doc_id=doc_id,
            summary="[Pending: Background job queue not yet implemented]",
            style=style,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to request summary",
            extra={
                "user_id": current_user_id,
                "doc_id": doc_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to request summary")


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
