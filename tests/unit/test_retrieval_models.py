"""Unit tests for retrieval query, filter, and evidence data models."""

import uuid

from backend.app.retrieval.models import (
    EvidenceChunk,
    RetrievalResult,
    SearchFilter,
    SearchQuery,
)


def test_retrieval_models_instantiation():
    """Verify instantiation and property access of retrieval models."""
    pid = uuid.uuid4()
    s_filter = SearchFilter(
        language="python",
        file_path_pattern="services/",
        chunk_types=["function", "method"],
        symbol_name="login",
    )
    assert s_filter.language == "python"
    assert s_filter.chunk_types == ["function", "method"]

    query = SearchQuery(
        query="authenticate user with token",
        project_id=pid,
        top_k=5,
        search_type="hybrid",
        filters=s_filter,
    )
    assert query.top_k == 5
    assert query.search_type == "hybrid"

    evidence = EvidenceChunk(
        chunk_id="chunk-123",
        file_path="services/auth.py",
        start_line=10,
        end_line=25,
        chunk_content="def login(token): ...",
        score=0.92,
        match_type="hybrid",
        symbol="login",
        parent_name="AuthService",
        metadata={"token_count": 15},
    )
    assert evidence.line_range == (10, 25)
    assert evidence.score == 0.92
    assert evidence.symbol == "login"

    result = RetrievalResult(
        query="authenticate user with token",
        project_id=pid,
        evidence=[evidence],
        total_found=1,
        search_type="hybrid",
        execution_time_ms=12.5,
    )
    assert result.total_found == 1
    assert result.evidence[0].chunk_id == "chunk-123"
