"""Pytest fixtures and configuration."""

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import create_app


@pytest.fixture(scope="session")
def app():
    """Create a FastAPI application instance for testing."""
    return create_app()


@pytest.fixture(scope="session")
def client(app) -> TestClient:
    """Provide a TestClient for testing HTTP endpoints."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async database session for repository tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from backend.app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
