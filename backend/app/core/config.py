"""Configuration settings management using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Annotated, Any

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: Any) -> list[str]:
    """Parse CORS origins whether provided as a JSON list, comma-separated string, or list."""
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in v.split(",") if item.strip()]
    if isinstance(v, (list, tuple)):
        return [str(item).strip() for item in v]
    return []


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General App Settings
    PROJECT_NAME: str = "AI Codebase Reviewer"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # CORS Settings
    BACKEND_CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors_origins)] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
    ]

    # Local PostgreSQL Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "codebase_reviewer"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "root"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:root@localhost:5432/codebase_reviewer"
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20
    POSTGRES_POOL_TIMEOUT: int = 30

    # Vector Embedding Settings
    # Default dimension matches standard OpenAI text-embedding-3-small (1536).
    # Configurable via EMBEDDING_DIMENSION env var for other embedding providers.
    EMBEDDING_DIMENSION: int = 1536

    # Ingestion & Security Guardrails
    MAX_ZIP_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_EXTRACTED_SIZE_BYTES: int = 250 * 1024 * 1024  # 250 MB (prevents zip bomb)
    MAX_FILES_COUNT: int = 10_000  # Max files allowed per project
    GITHUB_CLONE_TIMEOUT_SECONDS: int = 60
    TEMP_WORKSPACE_DIR: str | None = None

    # Semantic Chunking Configuration
    CHUNK_MAX_LINES: int = 120
    CHUNK_MIN_LINES: int = 5
    CHUNK_OVERLAP_LINES: int = 15
    CHUNK_MAX_CHARS: int = 4000

    # Frontend Settings
    FRONTEND_PORT: int = 8501
    BACKEND_API_URL: str = "http://127.0.0.1:8000"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Return synchronous database connection string for Alembic migrations."""
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()


settings = get_settings()
