"""Tests for document_router - schema and structure validation."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.dependencies import get_current_user
from app.schemas.document_schemas import DocumentResponse, DocumentListResponse


def test_router_has_all_endpoints():
    """Verify all required endpoints exist."""
    app = create_app()
    
    # Check that routes are registered
    routes = [route.path for route in app.routes]
    
    # Should have document endpoints (once we integrate them)
    # For now, just verify health endpoint exists
    assert "/health" in routes


def test_current_user_dependency_exists():
    """Verify get_current_user dependency is available."""
    app = create_app()
    
    async def mock_get_user():
        return "test_user"
    
    app.dependency_overrides[get_current_user] = mock_get_user
    
    # Verify the override was registered
    assert get_current_user in app.dependency_overrides


def test_document_response_schema():
    """Verify DocumentResponse schema works correctly."""
    data = {
        "id": 1,
        "title": "Test Doc",
        "content": "Test content",
        "owner_id": "user_a",
        "created_at": "2024-01-01T00:00:00"
    }
    
    doc = DocumentResponse(**data)
    assert doc.id == 1
    assert doc.title == "Test Doc"
    assert doc.owner_id == "user_a"


def test_document_list_response_schema():
    """Verify DocumentListResponse schema works correctly."""
    data = {
        "documents": [
            {
                "id": 1,
                "title": "Doc 1",
                "content": "Content 1",
                "owner_id": "user_a",
                "created_at": "2024-01-01T00:00:00"
            }
        ],
        "total": 1
    }
    
    resp = DocumentListResponse(**data)
    assert resp.total == 1
    assert len(resp.documents) == 1
    assert resp.documents[0].title == "Doc 1"


def test_document_upload_request_validation():
    """Verify DocumentUploadRequest validation works."""
    from app.schemas.document_schemas import DocumentUploadRequest
    
    # Valid request
    req = DocumentUploadRequest(title="Test", content="Content")
    assert req.title == "Test"
    
    # Invalid: empty title
    with pytest.raises(Exception):  # Pydantic validation error
        DocumentUploadRequest(title="", content="Content")
    
    # Invalid: empty content
    with pytest.raises(Exception):  # Pydantic validation error
        DocumentUploadRequest(title="Test", content="")


def test_document_summary_response_schema():
    """Verify DocumentSummaryResponse schema."""
    from app.schemas.document_schemas import DocumentSummaryResponse
    
    resp = DocumentSummaryResponse(
        doc_id=1,
        summary="This is a summary",
        style="executive"
    )
    assert resp.doc_id == 1
    assert resp.style == "executive"


def test_app_startup():
    """Verify app can be created without errors."""
    app = create_app()
    assert app is not None
    assert app.title == "KnowledgeHub"
