"""Document permission service (extracted from LegacyDocumentService)."""

from typing import Optional


class DocumentPermissionService:
    """Handles document permission checks."""

    def __init__(self, documents_store: dict):
        """
        Initialize with reference to documents store.

        Args:
            documents_store: dict mapping doc_id to document dict
        """
        self._documents = documents_store

    def can_access_document(self, doc_id: int, current_user_id: str) -> bool:
        """
        Check if user can access a document.

        Returns True only if document exists and user is the owner.
        """
        doc = self._documents.get(doc_id)
        if doc is None:
            return False
        return self._is_owner(doc, current_user_id)

    def can_delete_document(self, doc_id: int, current_user_id: str) -> bool:
        """
        Check if user can delete a document.

        Returns True only if document exists and user is the owner.
        """
        doc = self._documents.get(doc_id)
        if doc is None:
            return False
        return self._is_owner(doc, current_user_id)

    def _is_owner(self, doc: dict, current_user_id: str) -> bool:
        """Check if user is the owner of a document."""
        return doc.get("owner_id") == current_user_id

    def get_document_if_owned(
        self, doc_id: int, current_user_id: str
    ) -> Optional[dict]:
        """
        Retrieve a document if the user owns it, else return None.

        Used internally by LegacyDocumentService.
        """
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        if not self._is_owner(doc, current_user_id):
            return None
        return doc
