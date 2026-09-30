"""Vector embedding providers package."""

from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.deterministic_provider import (
    DeterministicCodeEmbeddingProvider,
)
from backend.app.retrieval.embeddings.factory import get_embedding_provider
from backend.app.retrieval.embeddings.fastembed_provider import FastEmbedEmbeddingProvider
from backend.app.retrieval.embeddings.mock_provider import MockEmbeddingProvider, RateLimitError

__all__ = [
    "BaseEmbeddingProvider",
    "DeterministicCodeEmbeddingProvider",
    "FastEmbedEmbeddingProvider",
    "MockEmbeddingProvider",
    "RateLimitError",
    "get_embedding_provider",
]
