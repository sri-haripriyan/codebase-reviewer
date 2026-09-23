"""Health check endpoint router."""

from fastapi import APIRouter, status

from backend.app.core.config import settings
from backend.app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns the health status and deployment metadata of the service.",
)
async def get_health() -> HealthResponse:
    """Return application health metadata."""
    return HealthResponse(
        status="healthy",
        app_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )
