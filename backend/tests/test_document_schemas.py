"""Regression tests: ORM Document must serialize into the API response schema."""

from datetime import datetime

from app.models.document import Document
from app.schemas.document_schemas import DocumentResponse


def _make_document(doc_metadata: str | None = None) -> Document:
    return Document(
        id=1,
        owner_id="user_a",
        filename="policy.txt",
        content="Passwords rotate every 90 days.",
        doc_metadata=doc_metadata,
        created_at=datetime(2026, 1, 1),
    )


def test_document_response_from_orm_document() -> None:
    response = DocumentResponse.model_validate(_make_document())

    assert response.id == 1
    assert response.owner_id == "user_a"
    assert response.filename == "policy.txt"
    assert response.doc_metadata is None


def test_document_response_exposes_doc_metadata() -> None:
    response = DocumentResponse.model_validate(_make_document('{"k": "v"}'))

    assert response.doc_metadata == '{"k": "v"}'
