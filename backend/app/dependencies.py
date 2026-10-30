"""FastAPI dependencies for injection."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings


# Global engine and session factory (created once per app startup)
_engine = None
_async_session_factory = None


async def init_db() -> None:
    """Initialize database engine and session factory (call on app startup)."""
    global _engine, _async_session_factory
    _engine = create_async_engine(settings.database_url, echo=False)
    _async_session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_db() -> None:
    """Close database connections (call on app shutdown)."""
    global _engine
    if _engine:
        await _engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency: Get an async database session.

    Usage in endpoint:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if not _async_session_factory:
        raise RuntimeError(
            "Database not initialized. Call init_db() on app startup."
        )
    async with _async_session_factory() as session:
        yield session


async def get_current_user() -> str:
    """
    Dependency: Get the current user ID from auth context.

    TODO: Implement actual JWT/session extraction.
    For now, returns a mock user ID for testing.

    In production, this should:
    1. Extract JWT from Authorization header or session cookie
    2. Verify signature
    3. Extract user_id from claims
    4. Raise HTTPException(401) if invalid

    Usage in endpoint:
        async def my_endpoint(current_user_id: str = Depends(get_current_user)):
            ...
    """
    # TODO (Step 2.1): Implement real auth
    # Stub for testing:
    return "user_a"
