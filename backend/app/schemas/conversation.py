"""Pydantic schemas for Conversation threads and Messages."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    """Response representation of a chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationResponse(BaseModel):
    """Response representation of a conversation thread with history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)
