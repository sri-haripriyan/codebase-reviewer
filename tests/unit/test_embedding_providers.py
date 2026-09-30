"""Unit tests for embedding providers, dimension adaptation, retries, and rate limits."""

import math
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.chunker.models import CodeChunk as DomainCodeChunk
from backend.app.repositories.code_chunk_repository import CodeChunkRepository
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.deterministic_provider import (
    DeterministicCodeEmbeddingProvider,
)
from backend.app.retrieval.embeddings.factory import get_embedding_provider
from backend.app.retrieval.embeddings.fastembed_provider import FastEmbedEmbeddingProvider
from backend.app.retrieval.embeddings.mock_provider import MockEmbeddingProvider
from backend.app.retrieval.indexer import ChunkIndexerService


def test_base_embedding_dimension_adaptation():
    """Verify vector dimension adaptation zero-pads and preserves unit norm."""
    # 1. Padding 4-d vector to 8-d
    vec_4 = [1.0, 0.0, 0.0, 0.0]
    adapted_8 = BaseEmbeddingProvider.adapt_dimension(vec_4, target_dim=8)
    assert len(adapted_8) == 8
    assert adapted_8[0] == pytest.approx(1.0)
    assert sum(adapted_8[4:]) == pytest.approx(0.0)
    norm = math.sqrt(sum(x * x for x in adapted_8))
    assert norm == pytest.approx(1.0)

    # 2. Truncating 8-d vector to 4-d
    vec_8 = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    adapted_4 = BaseEmbeddingProvider.adapt_dimension(vec_8, target_dim=4)
    assert len(adapted_4) == 4
    norm_4 = math.sqrt(sum(x * x for x in adapted_4))
    assert norm_4 == pytest.approx(1.0)


def test_deterministic_provider_semantic_similarity():
    """Verify that deterministic provider gives high similarity for related texts."""
    provider = DeterministicCodeEmbeddingProvider(dimension=1536)
    assert provider.dimension == 1536

    doc1 = "def authenticate_user(token: str): verify_jwt(token)"
    doc2 = "async def authenticate_user(jwt_token: str): return verify_jwt(jwt_token)"
    doc3 = "SELECT * FROM billing_invoices WHERE status = 'paid'"

    vec1 = provider.embed_query(doc1)
    vec2 = provider.embed_query(doc2)
    vec3 = provider.embed_query(doc3)

    assert len(vec1) == 1536
    assert len(vec2) == 1536
    assert len(vec3) == 1536

    # Cosine similarity between unit vectors is dot product
    sim_related = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    sim_unrelated = sum(a * b for a, b in zip(vec1, vec3, strict=True))

    assert sim_related > sim_unrelated
    assert sim_related > 0.2
    assert sim_unrelated < 0.1


def test_fastembed_provider():
    """Verify FastEmbed provider initialization and document embedding."""
    provider = FastEmbedEmbeddingProvider()
    assert provider.dimension > 0

    texts = [
        "def connect_db(): return psycopg.connect()",
        "class PaymentGateway: pass",
    ]
    embeddings = provider.embed_documents(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == provider.dimension

    query_vec = provider.embed_query("connect to database")
    assert len(query_vec) == provider.dimension


def test_provider_factory_resolution():
    """Verify factory returns appropriate provider based on string or settings."""
    det_provider = get_embedding_provider("deterministic", force_new=True)
    assert isinstance(det_provider, DeterministicCodeEmbeddingProvider)

    mock_provider = get_embedding_provider("mock", force_new=True)
    assert isinstance(mock_provider, MockEmbeddingProvider)

    fast_provider = get_embedding_provider("fastembed", force_new=True)
    assert isinstance(fast_provider, FastEmbedEmbeddingProvider)


@pytest.mark.asyncio
async def test_indexer_retry_on_transient_failure():
    """Verify ChunkIndexerService retries on transient network errors and recovers."""
    mock_provider = MockEmbeddingProvider(
        dimension=1536,
        transient_failures_remaining=2,  # Fail twice, then succeed on 3rd attempt
    )
    mock_repo = MagicMock(spec=CodeChunkRepository)
    mock_repo.bulk_create = AsyncMock(return_value=[MagicMock(), MagicMock()])

    indexer = ChunkIndexerService(
        repository=mock_repo,
        embedding_provider=mock_provider,
        max_retries=3,
        backoff_factor=0.01,
        target_dimension=1536,
    )

    chunks = [
        DomainCodeChunk(
            file_path="auth.py",
            language="python",
            content="def login(): ...",
            start_line=1,
            end_line=5,
            chunk_type="function",
        ),
        DomainCodeChunk(
            file_path="auth.py",
            language="python",
            content="def logout(): ...",
            start_line=7,
            end_line=10,
            chunk_type="function",
        ),
    ]

    result = await indexer.index_chunks(
        project_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        chunks=chunks,
    )

    assert len(result) == 2
    assert mock_provider.call_count == 3  # 2 failed attempts + 1 successful attempt
    assert mock_repo.bulk_create.called


@pytest.mark.asyncio
async def test_indexer_rate_limit_backoff():
    """Verify ChunkIndexerService handles simulated HTTP 429 rate limits gracefully."""
    mock_provider = MockEmbeddingProvider(
        dimension=1536,
        rate_limits_remaining=1,  # Hit 429 once, then succeed
    )
    mock_repo = MagicMock(spec=CodeChunkRepository)
    mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])

    indexer = ChunkIndexerService(
        repository=mock_repo,
        embedding_provider=mock_provider,
        max_retries=2,
        backoff_factor=0.01,
        target_dimension=1536,
    )

    chunks = [
        DomainCodeChunk(
            file_path="pay.py",
            language="python",
            content="class StripeService: ...",
            start_line=1,
            end_line=15,
            chunk_type="class",
        ),
    ]

    result = await indexer.index_chunks(
        project_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        chunks=chunks,
    )

    assert len(result) == 1
    assert mock_provider.call_count == 2  # 1 rate limit + 1 success


@pytest.mark.asyncio
async def test_indexer_raises_after_max_retries():
    """Verify ChunkIndexerService raises RuntimeError when errors exceed max_retries."""
    mock_provider = MockEmbeddingProvider(
        dimension=1536,
        transient_failures_remaining=5,  # Exceeds max_retries=2
    )
    mock_repo = MagicMock(spec=CodeChunkRepository)
    mock_repo.bulk_create = AsyncMock()

    indexer = ChunkIndexerService(
        repository=mock_repo,
        embedding_provider=mock_provider,
        max_retries=2,
        backoff_factor=0.01,
    )

    chunks = [
        DomainCodeChunk(
            file_path="fail.py",
            language="python",
            content="def will_fail(): ...",
            start_line=1,
            end_line=2,
            chunk_type="function",
        )
    ]

    with pytest.raises(RuntimeError, match="Failed to generate embeddings after 2 attempts"):
        await indexer.index_chunks(
            project_id=uuid.uuid4(),
            file_id=uuid.uuid4(),
            chunks=chunks,
        )


def test_indexer_deduplicates_identical_chunks():
    """Verify indexer deduplicates identical chunks based on content and line spans."""
    chunk1 = DomainCodeChunk(
        file_path="test.py",
        language="python",
        content="def dup(): pass",
        start_line=1,
        end_line=2,
        chunk_type="function",
    )
    # Identical content and line span
    chunk2 = DomainCodeChunk(
        file_path="test.py",
        language="python",
        content="def dup(): pass",
        start_line=1,
        end_line=2,
        chunk_type="function",
    )
    # Distinct chunk
    chunk3 = DomainCodeChunk(
        file_path="test.py",
        language="python",
        content="def other(): pass",
        start_line=4,
        end_line=5,
        chunk_type="function",
    )

    deduped = ChunkIndexerService._deduplicate_chunks([chunk1, chunk2, chunk3])
    assert len(deduped) == 2
    assert deduped[0] == chunk1
    assert deduped[1] == chunk3
