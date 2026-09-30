"""Pydantic schemas for conversational Q&A and code evidence citations."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchFilterSchema(BaseModel):
    """Optional metadata filters for search."""

    language: str | None = None
    file_path_pattern: str | None = None
    chunk_types: list[str] | None = None
    symbol_name: str | None = None


class ChatRequest(BaseModel):
    """Payload for conversational Q&A against a project's codebase."""

    message: str = Field(..., min_length=1, description="User question about the codebase")
    conversation_id: uuid.UUID | None = Field(
        None, description="Optional existing conversation thread ID to continue"
    )
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of code chunks to retrieve")
    filters: SearchFilterSchema | None = Field(None, description="Optional metadata filters")


class EvidenceReference(BaseModel):
    """Structured code snippet citation provided as evidence for an answer."""

    file_path: str
    symbol: str | None = None
    start_line: int
    end_line: int
    content: str
    score: float
    citation: str  # e.g., "[src/auth.py:10-25]"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response containing assistant answer and cited evidence."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    evidence: list[EvidenceReference]
    created_at: datetime
