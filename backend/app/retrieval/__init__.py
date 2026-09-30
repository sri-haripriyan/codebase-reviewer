"""Code retrieval and vector embeddings package."""

from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.factory import get_embedding_provider
from backend.app.retrieval.indexer import ChunkIndexerService
from backend.app.retrieval.models import (
    EvidenceChunk,
    RetrievalResult,
    SearchFilter,
    SearchQuery,
)
from backend.app.retrieval.service import RetrievalService

__all__ = [
    "BaseEmbeddingProvider",
    "ChunkIndexerService",
    "EvidenceChunk",
    "RetrievalResult",
    "RetrievalService",
    "SearchFilter",
    "SearchQuery",
    "get_embedding_provider",
]
