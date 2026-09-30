"""Factory for resolving and instantiating embedding providers."""

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.deterministic_provider import (
    DeterministicCodeEmbeddingProvider,
)
from backend.app.retrieval.embeddings.fastembed_provider import FastEmbedEmbeddingProvider
from backend.app.retrieval.embeddings.mock_provider import MockEmbeddingProvider

logger = get_logger(__name__)

_GLOBAL_PROVIDER: BaseEmbeddingProvider | None = None


def get_embedding_provider(
    provider_type: str | None = None,
    force_new: bool = False,
) -> BaseEmbeddingProvider:
    """Return an embedding provider instance based on provider_type or application settings."""
    global _GLOBAL_PROVIDER

    if not force_new and _GLOBAL_PROVIDER is not None and provider_type is None:
        return _GLOBAL_PROVIDER

    chosen = (provider_type or settings.EMBEDDING_PROVIDER).strip().lower()

    if chosen == "fastembed":
        try:
            provider = FastEmbedEmbeddingProvider()
        except Exception as e:
            logger.warning(
                "Failed to initialize FastEmbed (%s). Falling back to Deterministic.",
                e,
            )
            provider = DeterministicCodeEmbeddingProvider()
    elif chosen == "deterministic":
        provider = DeterministicCodeEmbeddingProvider()
    elif chosen == "mock":
        provider = MockEmbeddingProvider()
    else:
        logger.warning(
            "Unknown embedding provider '%s'. Defaulting to Deterministic provider.",
            chosen,
        )
        provider = DeterministicCodeEmbeddingProvider()

    if provider_type is None and not force_new:
        _GLOBAL_PROVIDER = provider

    return provider
