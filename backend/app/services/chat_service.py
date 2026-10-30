"""Chat service with streaming and permission checking."""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import DocumentRepository
from app.services.llm_client import LlmClient

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations with document ownership verification."""

    def __init__(self, db: AsyncSession, llm_client: LlmClient | None = None):
        """
        Initialize chat service.

        Args:
            db: Async SQLAlchemy session
            llm_client: LLM client for streaming (default: new instance)
        """
        self.db = db
        self.doc_repository = DocumentRepository(db)
        self.llm_client = llm_client or LlmClient()

    async def verify_document_ownership(
        self, document_ids: list[int], current_user_id: str
    ) -> bool:
        """
        Verify that all documents are owned by the current user.

        Args:
            document_ids: List of document IDs to check
            current_user_id: User ID claiming ownership

        Returns:
            True if all documents are owned by user, False otherwise
        """
        if not document_ids:
            return True  # Empty list is valid

        for doc_id in document_ids:
            doc = await self.doc_repository.get_by_id(doc_id)
            if not doc or doc.owner_id != current_user_id:
                logger.warning(
                    "Document ownership check failed",
                    extra={
                        "user_id": current_user_id,
                        "doc_id": doc_id,
                        "exists": doc is not None,
                    },
                )
                return False
        return True

    async def stream_answer(
        self,
        question: str,
        document_ids: list[int],
        current_user_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Stream an answer to a question grounded in documents.

        Yields SSE events: "token" events with content, then "done" event.
        On asyncio.CancelledError (client disconnect), upstream connection is closed.

        Args:
            question: User's question
            document_ids: Documents to use for grounding
            current_user_id: User making the request

        Yields:
            SSE event strings (JSON format)

        Raises:
            ValueError: If user doesn't own all documents
        """
        # Verify ownership
        owns_all = await self.verify_document_ownership(document_ids, current_user_id)
        if not owns_all:
            raise ValueError("User does not own all requested documents")

        logger.info(
            "Starting chat streaming",
            extra={
                "user_id": current_user_id,
                "question": question[:50],
                "doc_count": len(document_ids),
            },
        )

        # Build context from documents (simplified for now)
        context = self._build_context(document_ids)

        # Build messages for LLM
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer questions based only on "
                    "the provided document content. If the answer is not in the documents, "
                    "say so."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ]

        try:
            async for token in self.llm_client.stream_completion(messages):
                # Yield SSE event with token
                event = f'data: {{"event": "token", "data": "{self._escape_json(token)}"}}\n\n'
                yield event

            # Send done event
            yield 'data: {"event": "done", "data": null}\n\n'
            logger.info(
                "Chat streaming completed",
                extra={"user_id": current_user_id},
            )

        except Exception as e:
            logger.error(
                "Chat streaming error",
                extra={"user_id": current_user_id, "error": str(e)},
            )
            error_event = (
                f'data: {{"event": "error", "data": "{self._escape_json(str(e))}"}}\n\n'
            )
            yield error_event

    def _build_context(self, document_ids: list[int]) -> str:
        """
        Build context string from documents.

        TODO: In production, use RAG pipeline (Step 3.3):
        - Retrieve relevant chunks from pgvector
        - Format in delimited blocks
        - Include chunk metadata for citations

        For now, return placeholder.

        Args:
            document_ids: Document IDs

        Returns:
            Context string for LLM
        """
        if not document_ids:
            return "(No documents selected)"
        return f"(Documents: {', '.join(map(str, document_ids))})"

    def _escape_json(self, text: str) -> str:
        """Escape text for JSON string (for SSE data field)."""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
