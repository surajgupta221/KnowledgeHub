"""Compatibility exports for the document controller module name."""

from app.routers.document_router import (
    delete_document,
    get_document,
    list_documents,
    request_document_summary,
    router,
    upload_document,
)

__all__ = [
    "router",
    "upload_document",
    "list_documents",
    "get_document",
    "request_document_summary",
    "delete_document",
]
