"""Chat service with streaming and permission checking."""

import json
import logging
from typing import AsyncGenerator

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import DocumentRepository
from app.schemas.chat_schemas import RagAnswer
from app.services.llm_client import LlmClient, LlmUnavailableError
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations with document ownership verification."""

    def __init__(
        self,
        db: AsyncSession,
        llm_client: LlmClient | None = None,
        embedding_service: EmbeddingService | None = None,
        retrieval_service: RetrievalService | None = None,
    ):
        """
        Initialize chat service.

        Args:
            db: Async SQLAlchemy session
            llm_client: LLM client for streaming (default: new instance)
            embedding_service: Service for embedding questions (default: new instance)
            retrieval_service: Service for retrieving relevant chunks (default: new instance)
        """
        self.db = db
        self.doc_repository = DocumentRepository(db)
        self.llm_client = llm_client or LlmClient()
        self.embedding_service = embedding_service or EmbeddingService(db)
        # Hashed bag-of-words similarity between a short question and a long
        # chunk is small, so chat uses a low floor; top_k still bounds the context.
        self.retrieval_service = retrieval_service or RetrievalService(
            db, similarity_threshold=0.03
        )

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

        # Build context from documents using RAG pipeline
        context = await self._build_context(document_ids, question)

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
                yield self._sse("token", token)

            yield self._sse("done", None)
            logger.info(
                "Chat streaming completed",
                extra={"user_id": current_user_id},
            )

        except Exception as e:
            logger.error(
                "Chat streaming error",
                extra={"user_id": current_user_id, "error": str(e)},
            )
            # Generic message: never leak internals; LLM outages get a fallback
            message = (
                "The AI service is temporarily unavailable. Please try again shortly."
                if isinstance(e, LlmUnavailableError)
                else "Stream failed"
            )
            yield self._sse("error", message)

    @staticmethod
    def _sse(event: str, data: str | None) -> str:
        """Format one SSE message with proper JSON escaping."""
        return f"data: {json.dumps({'event': event, 'data': data})}\n\n"

    async def answer_structured(
        self,
        question: str,
        document_ids: list[int],
        current_user_id: str,
    ) -> RagAnswer:
        """
        Answer using retrieved chunks and enforce a strict JSON schema.

        The LLM output is validated with Pydantic; on invalid output one repair
        attempt is made before raising ValueError.
        """
        if not await self.verify_document_ownership(document_ids, current_user_id):
            raise ValueError("User does not own all requested documents")

        context = await self._build_context(document_ids, question)
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer only from the provided context. Respond with ONLY a JSON "
                    'object: {"answer": str, "confidence": number 0-1, "citations": '
                    '[{"document_id": int, "chunk_id": int, "quote": str}]}. '
                    "If the context lacks the answer, say so with confidence 0."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]

        last_error: Exception | None = None
        for _ in range(2):
            raw = "".join([t async for t in self.llm_client.stream_completion(messages)])
            try:
                return RagAnswer.model_validate_json(self._extract_json(raw))
            except ValidationError as exc:
                last_error = exc
                messages = messages + [
                    {"role": "assistant", "content": raw[:2000]},
                    {
                        "role": "user",
                        "content": "That was not valid against the schema. "
                        "Return ONLY the corrected JSON object.",
                    },
                ]
        raise ValueError("LLM returned invalid structured output") from last_error

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Strip code fences / surrounding prose around a JSON object."""
        start, end = raw.find("{"), raw.rfind("}")
        return raw[start : end + 1] if start != -1 and end > start else raw

    async def _build_context(self, document_ids: list[int], question: str) -> str:
        """
        Build context string from documents using RAG pipeline.

        Steps:
        1. Embed the user question
        2. Retrieve relevant chunks from selected documents
        3. Format chunks with citations

        Args:
            document_ids: Document IDs to search
            question: User's question to embed and search with

        Returns:
            Context string for LLM with citations
        """
        if not document_ids:
            return "(No documents selected)"

        try:
            # Step 1: Embed the question
            question_embeddings = await self.embedding_service._get_embeddings([question])
            if not question_embeddings:
                logger.warning("Failed to embed question")
                return f"(Documents: {', '.join(map(str, document_ids))})"

            question_embedding = question_embeddings[0]

            # Step 2: Retrieve relevant chunks
            retrieved_chunks = await self.retrieval_service.retrieve_relevant_chunks(
                query_embedding=question_embedding,
                document_ids=document_ids,
            )

            # Step 3: Format chunks for context
            if retrieved_chunks:
                context = await self.retrieval_service.format_retrieved_chunks(
                    retrieved_chunks
                )
                return context
            else:
                return f"(No relevant chunks found in {len(document_ids)} document(s))"

        except Exception as e:
            logger.error(
                "Error building RAG context",
                extra={"error": str(e), "doc_count": len(document_ids)},
            )
            return f"(Error retrieving context: {str(e)})"
