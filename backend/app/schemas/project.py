"""Pydantic schemas for Project creation and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Payload for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    source_type: str = Field("github", description="Source type: 'github' or 'zip'")
    source_url: str | None = Field(None, max_length=1024, description="Optional source URL")


class ProjectResponse(BaseModel):
    """Response representation of a project."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_type: str
    source_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
