"""Document repository (data access layer)."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    """Repository for document data access."""

    def __init__(self, db: AsyncSession):
        """
        Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        """
        Get a document by ID without permission checks.

        Permission checks happen in the service layer.

        Args:
            doc_id: Document ID

        Returns:
            Document ORM model or None
        """
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_owner(
        self, owner_id: str, limit: int = 100, offset: int = 0
    ) -> list[Document]:
        """
        Get all documents by owner (permission already checked by caller).

        Args:
            owner_id: Owner ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Document ORM models
        """
        result = await self.db.execute(
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
