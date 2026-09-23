"""Health check response schema."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Structured response schema for health check endpoints."""

    status: str = Field(default="healthy", description="Current service health status")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Current deployment environment")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the health check inspection",
    )
