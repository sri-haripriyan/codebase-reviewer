"""Data models for code retrieval, filters, queries, and evidence chunks."""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchFilter:
    """Metadata filters for scoping code retrieval queries."""

    language: str | None = None
    file_path_pattern: str | None = None
    chunk_types: list[str] | None = None
    symbol_name: str | None = None


@dataclass
class SearchQuery:
    """Request representation for code retrieval within a specific project."""

    query: str
    project_id: uuid.UUID
    top_k: int = 10
    search_type: str = "hybrid"  # "hybrid", "semantic", "lexical"
    filters: SearchFilter | None = None
    min_score: float | None = None


@dataclass
class EvidenceChunk:
    """Retrieved code chunk returned as evidence for Q&A or agent analysis."""

    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    chunk_content: str
    score: float  # Normalized relevance score (0.0 to 1.0)
    match_type: str = "semantic"  # "semantic", "lexical", "hybrid"
    symbol: str | None = None
    parent_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def line_range(self) -> tuple[int, int]:
        """Return (start_line, end_line) tuple."""
        return (self.start_line, self.end_line)


@dataclass
class RetrievalResult:
    """Container for search results returned by RetrievalService."""

    query: str
    project_id: uuid.UUID
    evidence: list[EvidenceChunk]
    total_found: int
    search_type: str
    execution_time_ms: float = 0.0
