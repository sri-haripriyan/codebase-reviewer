"""FastEmbed embedding provider using local ONNX runtime for efficient embeddings."""

from fastembed import TextEmbedding

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider

logger = get_logger(__name__)


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    """Generates dense vector embeddings using fastembed and ONNX runtime."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        logger.info("Initializing FastEmbedEmbeddingProvider with model: %s", self.model_name)
        self._model = TextEmbedding(model_name=self.model_name)
        # Determine native dimension
        sample = list(self._model.embed(["test"]))
        self._dimension = len(sample[0]) if sample else 384

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.embed(texts)
        return [self.normalize_vector(emb.tolist()) for emb in embeddings]
