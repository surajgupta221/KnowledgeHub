"""Database configuration and session management."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from contextlib import asynccontextmanager

from app.config import settings

# Convert postgresql:// URL to postgresql+asyncpg:// for async support
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    database_url,
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
        if conn.dialect.name == "postgresql":
            # pgvector ships in the compose image; enable it for similarity search
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
