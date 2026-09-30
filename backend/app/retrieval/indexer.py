"""Chunk indexing service with batching, retries, rate-limit handling, and persistence."""

import asyncio
import hashlib
import random
import time
import uuid
from typing import Any

from backend.app.chunker.models import CodeChunk as DomainCodeChunk
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.models.code_chunk import CodeChunk as DBCodeChunk
from backend.app.repositories.code_chunk_repository import CodeChunkRepository
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.factory import get_embedding_provider
from backend.app.retrieval.embeddings.mock_provider import RateLimitError

logger = get_logger(__name__)


class ChunkIndexerService:
    """Indexes source code chunks into PostgreSQL pgvector with batching and resilience."""

    def __init__(
        self,
        repository: CodeChunkRepository,
        embedding_provider: BaseEmbeddingProvider | None = None,
        batch_size: int | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
        target_dimension: int | None = None,
    ) -> None:
        self.repository = repository
        self.provider = embedding_provider or get_embedding_provider()
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.max_retries = max_retries or settings.EMBEDDING_MAX_RETRIES
        self.backoff_factor = backoff_factor or settings.EMBEDDING_RETRY_BACKOFF_FACTOR
        self.target_dimension = target_dimension or settings.EMBEDDING_DIMENSION

    async def _embed_batch_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with exponential backoff retry and rate-limit handling."""
        attempt = 0
        last_exception: Exception | None = None

        while attempt <= self.max_retries:
            try:
                # Synchronous or thread-executed embedding
                raw_embeddings = await asyncio.to_thread(self.provider.embed_documents, texts)
                # Adapt dimensions to target_dimension
                adapted = [
                    self.provider.adapt_dimension(emb, self.target_dimension)
                    for emb in raw_embeddings
                ]
                return adapted

            except RateLimitError as rle:
                attempt += 1
                last_exception = rle
                retry_after = getattr(rle, "retry_after", 0.5)
                logger.warning(
                    "Rate limit hit during embedding (attempt %d/%d). Backing off for %.2fs: %s",
                    attempt,
                    self.max_retries,
                    retry_after,
                    rle,
                )
                if attempt > self.max_retries:
                    break
                await asyncio.sleep(retry_after)

            except Exception as e:
                attempt += 1
                last_exception = e
                backoff = self.backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.01, 0.05)
                logger.warning(
                    "Transient embedding error (attempt %d/%d). Retrying in %.2fs: %s",
                    attempt,
                    self.max_retries,
                    backoff,
                    e,
                )
                if attempt > self.max_retries:
                    break
                await asyncio.sleep(backoff)

        logger.error(
            "Embedding failed after %d retries. Last error: %s",
            self.max_retries,
            last_exception,
        )
        raise RuntimeError(
            f"Failed to generate embeddings after {self.max_retries} attempts: {last_exception}"
        ) from last_exception

    @staticmethod
    def _deduplicate_chunks(
        chunks: list[DomainCodeChunk | dict[str, Any]],
    ) -> list[DomainCodeChunk | dict[str, Any]]:
        """Remove exact duplicate chunks based on content hash and line boundaries."""
        seen = set()
        deduped = []
        for c in chunks:
            content = c.content if isinstance(c, DomainCodeChunk) else c.get("content", "")
            s_line = c.start_line if isinstance(c, DomainCodeChunk) else c.get("start_line", 0)
            e_line = c.end_line if isinstance(c, DomainCodeChunk) else c.get("end_line", 0)
            h = hashlib.sha256(f"{content}:{s_line}:{e_line}".encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(c)
        return deduped

    async def index_chunks(
        self,
        project_id: uuid.UUID,
        file_id: uuid.UUID,
        chunks: list[DomainCodeChunk | dict[str, Any]],
    ) -> list[DBCodeChunk]:
        """Process, embed, and persist code chunks into PostgreSQL pgvector."""
        if not chunks:
            return []

        start_time = time.perf_counter()
        unique_chunks = self._deduplicate_chunks(chunks)
        total_chunks = len(unique_chunks)
        all_created: list[DBCodeChunk] = []

        logger.info(
            "Indexing %d chunks (deduped from %d) for file %s in project %s",
            total_chunks,
            len(chunks),
            file_id,
            project_id,
        )

        # Process in batches
        for i in range(0, total_chunks, self.batch_size):
            batch_slice = unique_chunks[i : i + self.batch_size]

            # Extract content strings for embedding
            batch_texts = [
                c.content if isinstance(c, DomainCodeChunk) else c["content"] for c in batch_slice
            ]

            # Generate embeddings with retry handling
            embeddings = await self._embed_batch_with_retry(batch_texts)

            # Build database payload
            batch_data: list[dict[str, Any]] = []
            for item, emb in zip(batch_slice, embeddings, strict=True):
                if isinstance(item, DomainCodeChunk):
                    chunk_type = item.chunk_type
                    symbol_name = item.symbol_name
                    parent_name = item.parent_name
                    content = item.content
                    start_line = item.start_line
                    end_line = item.end_line
                    metadata = item.metadata
                else:
                    chunk_type = item.get("chunk_type", "block")
                    symbol_name = item.get("symbol_name")
                    parent_name = item.get("parent_name")
                    content = item["content"]
                    start_line = item["start_line"]
                    end_line = item["end_line"]
                    metadata = item.get("metadata", {})

                class_name = parent_name if chunk_type in ("method", "class") else None
                function_name = symbol_name if chunk_type in ("function", "method") else None

                batch_data.append(
                    {
                        "file_id": file_id,
                        "content": content,
                        "start_line": start_line,
                        "end_line": end_line,
                        "chunk_type": chunk_type,
                        "symbol_name": symbol_name,
                        "class_name": class_name,
                        "function_name": function_name,
                        "meta": metadata,
                        "embedding": emb,
                    }
                )

            # Persist batch to PostgreSQL
            created = await self.repository.bulk_create(project_id, batch_data)
            all_created.extend(created)

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Successfully indexed and persisted %d chunks in %.3fs for project %s",
            len(all_created),
            elapsed,
            project_id,
        )
        return all_created
