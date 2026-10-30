"""Database configuration and session management."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from contextlib import asynccontextmanager

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Get a database session."""
    async with async_session_factory() as session:
        return session


@asynccontextmanager
async def get_session_context():
    """Context manager for database session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Initialize database (create tables)."""
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
