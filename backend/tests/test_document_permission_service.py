"""Unit tests for DocumentPermissionService."""

import pytest

from app.services.document_permission_service import DocumentPermissionService


@pytest.fixture
def documents_store():
    """Create a mock documents store."""
    return {
        1: {"id": 1, "owner_id": "user_a", "title": "Policy A"},
        2: {"id": 2, "owner_id": "user_b", "title": "Policy B"},
    }


@pytest.fixture
def permission_service(documents_store):
    """Create a permission service with test data."""
    return DocumentPermissionService(documents_store)


class TestDocumentPermissionService:
    """Unit tests for permission checking."""

    def test_owner_can_access_document(self, permission_service):
        """Owner can access their document."""
        assert permission_service.can_access_document(1, "user_a") is True

    def test_non_owner_cannot_access(self, permission_service):
        """Non-owner cannot access document."""
        assert permission_service.can_access_document(1, "user_b") is False

    def test_nonexistent_document_cannot_be_accessed(self, permission_service):
        """Nonexistent document cannot be accessed."""
        assert permission_service.can_access_document(999, "user_a") is False

    def test_owner_can_delete_document(self, permission_service):
        """Owner can delete their document."""
        assert permission_service.can_delete_document(1, "user_a") is True

    def test_non_owner_cannot_delete(self, permission_service):
        """Non-owner cannot delete document."""
        assert permission_service.can_delete_document(1, "user_b") is False

    def test_nonexistent_document_cannot_be_deleted(self, permission_service):
        """Nonexistent document cannot be deleted."""
        assert permission_service.can_delete_document(999, "user_a") is False

    def test_get_document_if_owned_success(self, permission_service):
        """get_document_if_owned returns document for owner."""
        doc = permission_service.get_document_if_owned(1, "user_a")
        assert doc is not None
        assert doc["id"] == 1

    def test_get_document_if_owned_non_owner(self, permission_service):
        """get_document_if_owned returns None for non-owner."""
        doc = permission_service.get_document_if_owned(1, "user_b")
        assert doc is None

    def test_get_document_if_owned_nonexistent(self, permission_service):
        """get_document_if_owned returns None for nonexistent document."""
        doc = permission_service.get_document_if_owned(999, "user_a")
        assert doc is None
