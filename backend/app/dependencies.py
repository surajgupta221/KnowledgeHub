"""FastAPI dependencies for injection."""

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory


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
    if not user_id:
        # Fallback for testing
        user_id = "user_a"
    return user_id
