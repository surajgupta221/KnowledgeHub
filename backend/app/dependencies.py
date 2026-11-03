"""FastAPI dependencies for injection."""

import re
from typing import AsyncGenerator

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.llm_client import LlmClient

USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency: Get an async database session.

    Usage in endpoint:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if not async_session_factory:
        raise RuntimeError(
            "Database not initialized."
        )
    async with async_session_factory() as session:
        yield session


async def get_current_user(request: Request) -> str:
    """
    Dependency: Get the current user ID from auth context.

    Reads from X-User-ID header (set by frontend in login).

    In production, this should:
    1. Extract JWT from Authorization header or session cookie
    2. Verify signature
    3. Extract user_id from claims
    4. Raise HTTPException(401) if invalid

    Usage in endpoint:
        async def my_endpoint(current_user_id: str = Depends(get_current_user)):
            ...
    """
    user_id = request.headers.get("X-User-ID")
    if not user_id or not USER_ID_PATTERN.fullmatch(user_id):
        raise HTTPException(status_code=401, detail="Missing or invalid user identity")
    return user_id


def get_llm_client(request: Request) -> LlmClient:
    """Dependency: the application-wide LLM client (shares the circuit breaker)."""
    state = request.app.state
    if getattr(state, "llm_client", None) is None:
        state.llm_client = LlmClient()
    client: LlmClient = state.llm_client
    return client
