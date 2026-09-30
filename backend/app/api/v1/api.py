"""API v1 router aggregator."""

from fastapi import APIRouter

from backend.app.api.v1.endpoints import health, projects

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects", "Chat"])
