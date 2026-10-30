"""Document service (production version with repository and real database access)."""

import logging
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document operations with permission checks."""

    def __init__(self, db: AsyncSession):
        """
        Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
        self.repository = DocumentRepository(db)

    async def create_document(
        self, filename: str, content: str, owner_id: str
    ) -> Document:
        """
        Create a new document owned by the current user.

        Args:
            filename: Document filename
            content: Document content
            owner_id: ID of the user creating the document

        Returns:
            Document ORM model (wrapped in schema by router)
        """
        doc = Document(filename=filename, content=content, owner_id=owner_id)
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_document(
        self, doc_id: int, current_user_id: str
    ) -> Optional[Document]:
        """
        Get a document if the current user owns it.

        Returns None if:
        - Document doesn't exist
        - Current user doesn't own it

        Args:
            doc_id: Document ID
            current_user_id: User requesting the document

        Returns:
            Document ORM model or None
        """
        doc = await self.repository.get_by_id(doc_id)
        if not doc or doc.owner_id != current_user_id:
            return None
        return doc

    async def list_documents_for_user(
        self, current_user_id: str, limit: int = 20, offset: int = 0
    ) -> Tuple[list[Document], int]:
        """
        List documents owned by a user with pagination.

        Filtering happens in SQL query (WHERE owner_id = :user_id), not in Python.

        Args:
            current_user_id: User ID
            limit: Maximum documents to return (1-100)
            offset: Pagination offset

        Returns:
            Tuple of (documents, total_count)
        """
        query = select(Document).where(Document.owner_id == current_user_id)
        result = await self.db.execute(query)
        total = len(result.scalars().all())

        # Paginated query
        query_paginated = (
            select(Document)
            .where(Document.owner_id == current_user_id)
            .order_by(Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query_paginated)
        docs = result.scalars().all()
        return list(docs), total

    async def delete_document(
        self, doc_id: int, current_user_id: str
    ) -> bool:
        """
        Delete a document if the current user owns it.

        Returns False if:
        - Document doesn't exist
        - Current user doesn't own it

        Args:
            doc_id: Document ID
            current_user_id: User requesting deletion

        Returns:
            True if deleted, False if not owned or not found
        """
        doc = await self.repository.get_by_id(doc_id)
        if not doc or doc.owner_id != current_user_id:
            return False
        await self.db.delete(doc)
        await self.db.commit()
        return True

    async def create_summary_job(self, doc_id: int, current_user_id: str) -> Optional[int]:
        """
        Create a background job to summarize a document.

        Returns job ID if document exists and user owns it, None otherwise.

        Args:
            doc_id: Document ID
            current_user_id: User requesting summary

        Returns:
            Job ID or None if document not found or not owned
        """
        from app.services.job_service import JobService

        doc = await self.get_document(doc_id, current_user_id)
        if not doc:
            return None

        job_service = JobService(self.db)
        job = await job_service.create_summary_job(doc_id, current_user_id)
        await job_service.commit()

        return job.id

