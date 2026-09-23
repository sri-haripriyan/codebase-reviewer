"""Unit tests for configuration settings."""

import os
from unittest.mock import patch

from backend.app.core.config import Settings, parse_cors_origins


def test_default_settings():
    """Verify that default settings load as expected."""
    settings = Settings()
    assert settings.PROJECT_NAME == "AI Codebase Reviewer"
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is True
    assert settings.API_V1_STR == "/api/v1"
    assert settings.PORT == 8000
    assert "localhost" in settings.POSTGRES_SERVER


def test_cors_parser_json_list():
    """Verify CORS origins parsing from JSON list string."""
    origins = parse_cors_origins('["http://localhost:3000", "http://localhost:8501"]')
    assert origins == ["http://localhost:3000", "http://localhost:8501"]


def test_cors_parser_comma_separated():
    """Verify CORS origins parsing from comma-separated string."""
    origins = parse_cors_origins("http://example.com, http://test.com")
    assert origins == ["http://example.com", "http://test.com"]


def test_cors_parser_direct_list():
    """Verify CORS origins parsing when already a list."""
    origins = parse_cors_origins(["http://a.com", "http://b.com"])
    assert origins == ["http://a.com", "http://b.com"]


def test_env_override():
    """Verify environment variable overrides."""
    with patch.dict(os.environ, {"PROJECT_NAME": "Custom Reviewer", "PORT": "9000"}):
        settings = Settings()
        assert settings.PROJECT_NAME == "Custom Reviewer"
        assert settings.PORT == 9000
