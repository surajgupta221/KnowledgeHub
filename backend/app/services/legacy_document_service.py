"""Legacy document service with permission logic delegated to DocumentPermissionService."""

from typing import Optional

from app.services.document_permission_service import DocumentPermissionService


class LegacyDocumentService:
    """Document service with permission checks delegated to injected service."""

    def __init__(
        self,
        permission_service: Optional[DocumentPermissionService] = None,
    ):
        """
        Initialize with mock data store and optional permission service.

        Args:
            permission_service: DocumentPermissionService for permission checks.
                If None, a new instance is created with the mock store.
        """
        self._documents = {
            1: {"id": 1, "owner_id": "user_a", "title": "Policy A", "content": "..."},
            2: {"id": 2, "owner_id": "user_b", "title": "Policy B", "content": "..."},
            3: {"id": 3, "owner_id": "user_a", "title": "Policy C", "content": "..."},
        }
        if permission_service is None:
            permission_service = DocumentPermissionService(self._documents)
        self._permission_service = permission_service

    def get_document(self, doc_id: int, current_user_id: str) -> Optional[dict]:
        """Get a document if the user owns it."""
        return self._permission_service.get_document_if_owned(doc_id, current_user_id)

    def list_documents(self, current_user_id: str) -> list[dict]:
        """List all documents owned by the current user."""
        return [
            doc
            for doc in self._documents.values()
            if doc["owner_id"] == current_user_id
        ]

    def delete_document(self, doc_id: int, current_user_id: str) -> bool:
        """Delete a document if the user owns it. Return True if deleted."""
        if not self._permission_service.can_delete_document(
            doc_id, current_user_id
        ):
            return False
        del self._documents[doc_id]
        return True

    def can_access_document(self, doc_id: int, current_user_id: str) -> bool:
        """Check if user can access a document."""
        return self._permission_service.can_access_document(doc_id, current_user_id)

    def can_delete_document(self, doc_id: int, current_user_id: str) -> bool:
        """Check if user can delete a document."""
        return self._permission_service.can_delete_document(doc_id, current_user_id)
