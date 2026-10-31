"""Chat router with streaming endpoint."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.chat_schemas import ChatStreamRequest
from app.services.chat_service import ChatService
from app.services.llm_client import LlmClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def stream_chat(
    http_request: Request,
    request: ChatStreamRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Stream chat completion as Server-Sent Events (SSE).

    Request body:
    {
        "question": "What is in this policy?",
        "document_ids": [1, 2, 3]
    }

    Response: text/event-stream with events:
    - event: "token", data: token string
    - event: "done", data: null (when complete)
    - event: "error", data: error message (on failure)

    Headers:
    - Cache-Control: no-cache (prevent caching of stream)
    - X-Accel-Buffering: no (disable nginx buffering)

    Client disconnect handling:
    - On asyncio.CancelledError, upstream LLM connection is closed
    - Resources are properly cleaned up

    Args:
        http_request: Raw request, used to detect client disconnects
        request: ChatStreamRequest with question and document_ids
        current_user_id: Current user (from auth context)
        db: Database session

    Returns:
        StreamingResponse with text/event-stream media type
    """
    try:
        service = ChatService(db, LlmClient())

        # Verify user owns all requested documents
        owns_all = await service.verify_document_ownership(
            request.document_ids, current_user_id
        )
        if not owns_all:
            logger.warning(
                "Unauthorized document access",
                extra={
                    "user_id": current_user_id,
                    "doc_ids": request.document_ids,
                },
            )
            raise HTTPException(
                status_code=403, detail="You do not own all requested documents"
            )

        logger.info(
            "Chat stream started",
            extra={
                "user_id": current_user_id,
                "question": request.question[:50],
                "doc_count": len(request.document_ids),
            },
        )

        # Create async generator that streams tokens
        async def generate_events():
            """
            Generate SSE events from chat stream.

            On client disconnect (http_request.is_disconnected()), the generator
            will exit and the upstream LLM connection will be closed by the
            async context manager in stream_answer().
            """
            try:
                async for event in service.stream_answer(
                    request.question,
                    request.document_ids,
                    current_user_id,
                ):
                    # Check if client disconnected
                    if await http_request.is_disconnected():
                        logger.info(
                            "Client disconnected, stopping stream",
                            extra={"user_id": current_user_id},
                        )
                        break
                    yield event
            except Exception as e:
                logger.error(
                    "Stream generation failed",
                    extra={"user_id": current_user_id, "error": str(e)},
                )
                error_event = (
                    f"data: {json.dumps({'event': 'error', 'data': 'Stream failed'})}\n\n"
                )
                yield error_event

        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Chat stream endpoint error",
            extra={"user_id": current_user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to start chat stream")
