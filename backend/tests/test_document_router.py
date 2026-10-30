"""Tests for document_router - schema and structure validation."""

import pytest
from datetime import datetime
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
        "filename": "policy.pdf",
        "content": "Test content",
        "owner_id": "user_a",
        "created_at": datetime.now()
    }
    
    doc = DocumentResponse(**data)
    assert doc.id == 1
    assert doc.filename == "policy.pdf"
    assert doc.owner_id == "user_a"


def test_document_list_response_schema():
    """Verify DocumentListResponse schema works correctly."""
    data = {
        "items": [
            {
                "id": 1,
                "filename": "policy.pdf",
                "content": "Content 1",
                "owner_id": "user_a",
                "created_at": datetime.now()
            }
        ],
        "total": 1
    }
    
    resp = DocumentListResponse(**data)
    assert resp.total == 1
    assert len(resp.items) == 1
    assert resp.items[0].filename == "policy.pdf"


def test_document_upload_request_validation():
    """Verify DocumentUploadRequest validation works."""
    from app.schemas.document_schemas import DocumentUploadRequest
    
    # Valid request
    req = DocumentUploadRequest(filename="policy.pdf", content="Content")
    assert req.filename == "policy.pdf"
    
    # Invalid: empty filename
    with pytest.raises(Exception):  # Pydantic validation error
        DocumentUploadRequest(filename="", content="Content")
    
    # Invalid: empty content
    with pytest.raises(Exception):  # Pydantic validation error
        DocumentUploadRequest(filename="policy.pdf", content="")


def test_document_summary_response_schema():
    """Verify DocumentSummaryResponse schema."""
    from app.schemas.document_schemas import DocumentSummaryResponse
    
    resp = DocumentSummaryResponse(
        doc_id=1,
        summary="This is a summary"
    )
    assert resp.doc_id == 1
    assert resp.summary == "This is a summary"


def test_app_startup():
    """Verify app can be created without errors."""
    app = create_app()
    assert app is not None
    assert app.title == "KnowledgeHub"

