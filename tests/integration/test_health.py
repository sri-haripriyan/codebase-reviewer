"""Integration tests for health endpoints."""

from fastapi.testclient import TestClient


def test_root_health_endpoint(client: TestClient):
    """Verify that root /health endpoint returns 200 OK and valid health schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data


def test_api_v1_health_endpoint(client: TestClient):
    """Verify that /api/v1/health endpoint returns 200 OK and valid health schema."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data


def test_cors_headers(client: TestClient):
    """Verify CORS headers are returned for allowed origins."""
    headers = {"Origin": "http://localhost:8501"}
    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8501"
