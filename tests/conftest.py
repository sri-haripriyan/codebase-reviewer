"""Pytest fixtures and configuration."""

import pytest
from fastapi.testclient import TestClient

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
