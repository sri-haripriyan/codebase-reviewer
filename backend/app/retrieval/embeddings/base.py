"""Abstract base class for vector embedding providers with dimension adaptation."""

import math
from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract interface for text and code embedding providers."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Compute dense vector embeddings for a list of documents/code chunks."""
        pass

    def embed_query(self, text: str) -> list[float]:
        """Compute dense vector embedding for a single search query."""
        results = self.embed_documents([text])
        if not results:
            raise ValueError("Embedding provider returned empty result for query")
        return results[0]

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the native vector dimension of the embedding model."""
        pass

    @staticmethod
    def normalize_vector(vector: list[float]) -> list[float]:
        """L2-normalize a vector so its Euclidean length is 1.0."""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-12:
            return [x / norm for x in vector]
        return vector

    @classmethod
    def adapt_dimension(cls, vector: list[float], target_dim: int) -> list[float]:
        """Align an embedding vector to target_dim via zero-padding or truncation.

        Guarantees exact dimension matching with the database schema while
        preserving vector direction and unit norm.
        """
        current_len = len(vector)
        if current_len == target_dim:
            return cls.normalize_vector(vector)
        elif current_len < target_dim:
            padded = list(vector) + [0.0] * (target_dim - current_len)
            return cls.normalize_vector(padded)
        else:
            truncated = vector[:target_dim]
            return cls.normalize_vector(truncated)
