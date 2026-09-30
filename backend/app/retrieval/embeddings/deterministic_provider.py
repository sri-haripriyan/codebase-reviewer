"""Deterministic semantic hash-based embedding provider for testing and offline use."""

import hashlib
import re

from backend.app.core.config import settings
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider


class DeterministicCodeEmbeddingProvider(BaseEmbeddingProvider):
    """Generates deterministic dense vector embeddings using token feature hashing.

    Produces high cosine similarity for texts sharing code keywords and symbols
    with zero network or heavyweight model dependencies.
    """

    def __init__(self, dimension: int | None = None) -> None:
        self._dim = dimension or settings.EMBEDDING_DIMENSION

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        if not text:
            return vec

        # Tokenize code into words, symbols, and bigrams
        tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
        if not tokens:
            return vec

        # Unigrams + Bigrams
        features = list(tokens)
        for i in range(len(tokens) - 1):
            features.append(f"{tokens[i]}_{tokens[i + 1]}")

        for feat in features:
            h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vec[idx] += sign

        return self.normalize_vector(vec)
