"""Mock embedding provider for unit testing retries, rate limits, and failure handling."""

from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider


class RateLimitError(Exception):
    """Simulates rate limit (HTTP 429) from an embedding API."""

    def __init__(
        self,
        message: str = "Rate limit exceeded (HTTP 429)",
        retry_after: float = 0.1,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock provider with controllable transient failures, rate limits, and custom vectors."""

    def __init__(
        self,
        dimension: int = 1536,
        transient_failures_remaining: int = 0,
        rate_limits_remaining: int = 0,
        custom_vectors: dict[str, list[float]] | None = None,
    ) -> None:
        self._dim = dimension
        self.transient_failures_remaining = transient_failures_remaining
        self.rate_limits_remaining = rate_limits_remaining
        self.custom_vectors = custom_vectors or {}
        self.call_count = 0
        self.embedded_texts_count = 0

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.embedded_texts_count += len(texts)

        # Simulate rate limit if configured
        if self.rate_limits_remaining > 0:
            self.rate_limits_remaining -= 1
            raise RateLimitError("Simulated 429 Too Many Requests", retry_after=0.01)

        # Simulate transient network/timeout error if configured
        if self.transient_failures_remaining > 0:
            self.transient_failures_remaining -= 1
            raise ConnectionError("Simulated transient connection timeout")

        results: list[list[float]] = []
        for idx, text in enumerate(texts):
            if text in self.custom_vectors:
                results.append(self.normalize_vector(self.custom_vectors[text]))
            else:
                # Default pseudo-vector based on index and length
                vec = [0.0] * self._dim
                vec[idx % self._dim] = 1.0
                results.append(self.normalize_vector(vec))

        return results
