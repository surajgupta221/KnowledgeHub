"""Characterization tests for permission behavior in LegacyDocumentService.

These tests document the current behavior before refactoring.
Goal: Extract permission logic into DocumentPermissionService with zero behavior change.
"""

import pytest

from app.services.legacy_document_service import LegacyDocumentService


@pytest.fixture
def service():
    """Create a fresh service for each test."""
    return LegacyDocumentService()


class TestDocumentPermissions:
    """Test suite for document permission behavior."""

    def test_owner_can_get_own_document(self, service):
        """Owner can retrieve their own document."""
        doc = service.get_document(doc_id=1, current_user_id="user_a")
        assert doc is not None
        assert doc["id"] == 1
        assert doc["owner_id"] == "user_a"

    def test_non_owner_cannot_get_document(self, service):
        """Non-owner cannot retrieve another user's document (returns None)."""
        doc = service.get_document(doc_id=1, current_user_id="user_b")
        assert doc is None

    def test_nonexistent_document_returns_none(self, service):
        """Nonexistent document returns None for any user."""
        doc = service.get_document(doc_id=999, current_user_id="user_a")
        assert doc is None

    def test_owner_can_list_own_documents(self, service):
        """Owner sees only their own documents in list."""
        docs = service.list_documents(current_user_id="user_a")
        assert len(docs) == 2
        assert all(d["owner_id"] == "user_a" for d in docs)
        assert {d["id"] for d in docs} == {1, 3}

    def test_other_user_cannot_see_documents(self, service):
        """User sees only their documents, not others'."""
        docs = service.list_documents(current_user_id="user_b")
        assert len(docs) == 1
        assert docs[0]["id"] == 2

    def test_user_with_no_documents_gets_empty_list(self, service):
        """User with no documents gets empty list."""
        docs = service.list_documents(current_user_id="user_c")
        assert docs == []

    def test_owner_can_delete_own_document(self, service):
        """Owner can delete their own document."""
        deleted = service.delete_document(doc_id=1, current_user_id="user_a")
        assert deleted is True
        # Verify it's actually gone
        doc = service.get_document(doc_id=1, current_user_id="user_a")
        assert doc is None

    def test_non_owner_cannot_delete_document(self, service):
        """Non-owner cannot delete another user's document."""
        deleted = service.delete_document(doc_id=1, current_user_id="user_b")
        assert deleted is False
        # Verify document still exists
        doc = service.get_document(doc_id=1, current_user_id="user_a")
        assert doc is not None

    def test_delete_nonexistent_document_fails(self, service):
        """Deleting a nonexistent document returns False."""
        deleted = service.delete_document(doc_id=999, current_user_id="user_a")
        assert deleted is False

    def test_can_access_document_owner_check(self, service):
        """can_access_document returns True only for owner."""
        assert service.can_access_document(doc_id=1, current_user_id="user_a") is True
        assert service.can_access_document(doc_id=1, current_user_id="user_b") is False

    def test_can_access_document_nonexistent(self, service):
        """can_access_document returns False for nonexistent document."""
        assert service.can_access_document(doc_id=999, current_user_id="user_a") is False

    def test_can_delete_document_owner_check(self, service):
        """can_delete_document returns True only for owner."""
        assert service.can_delete_document(doc_id=1, current_user_id="user_a") is True
        assert service.can_delete_document(doc_id=1, current_user_id="user_b") is False

    def test_can_delete_document_nonexistent(self, service):
        """can_delete_document returns False for nonexistent document."""
        assert service.can_delete_document(doc_id=999, current_user_id="user_a") is False
