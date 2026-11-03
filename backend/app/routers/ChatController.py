"""Compatibility exports for the chat controller module name."""

from app.routers.chat_router import router, stream_chat

__all__ = ["router", "stream_chat"]
