"""Database engine and session management for async and sync operations."""

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import settings

# Asynchronous engine for application runtime & FastAPI dependencies
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=False,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an async database session for request lifecycle."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_engine(url: str | None = None) -> Engine:
    """Create a synchronous engine for Alembic migrations and CLI tasks."""
    sync_url = url or settings.SYNC_DATABASE_URL
    return create_engine(
        sync_url,
        pool_pre_ping=True,
        echo=False,
    )
