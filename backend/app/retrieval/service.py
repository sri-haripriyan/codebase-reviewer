"""RetrievalService providing semantic, lexical, and hybrid code search with project isolation."""

import asyncio
import time
import uuid

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.models.code_chunk import CodeChunk as DBCodeChunk
from backend.app.repositories.code_chunk_repository import CodeChunkRepository
from backend.app.retrieval.embeddings.base import BaseEmbeddingProvider
from backend.app.retrieval.embeddings.factory import get_embedding_provider
from backend.app.retrieval.models import (
    EvidenceChunk,
    RetrievalResult,
    SearchFilter,
    SearchQuery,
)

logger = get_logger(__name__)


class RetrievalService:
    """Service orchestrating semantic, lexical, and hybrid code retrieval."""

    def __init__(
        self,
        repository: CodeChunkRepository,
        embedding_provider: BaseEmbeddingProvider | None = None,
        default_top_k: int | None = None,
        similarity_threshold: float | None = None,
        hybrid_alpha: float | None = None,
        target_dimension: int | None = None,
    ) -> None:
        self.repository = repository
        self.provider = embedding_provider or get_embedding_provider()
        self.default_top_k = default_top_k or settings.RETRIEVAL_TOP_K
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.RETRIEVAL_SIMILARITY_THRESHOLD
        )
        self.hybrid_alpha = (
            hybrid_alpha if hybrid_alpha is not None else settings.RETRIEVAL_HYBRID_ALPHA
        )
        self.target_dimension = target_dimension or settings.EMBEDDING_DIMENSION

    async def search(self, request: SearchQuery) -> RetrievalResult:
        """Execute a search query adhering to the requested search_type and filters."""
        start_time = time.perf_counter()
        search_type = request.search_type.lower()
        top_k = request.top_k or self.default_top_k

        if search_type == "semantic":
            evidence = await self.semantic_search(
                project_id=request.project_id,
                query=request.query,
                top_k=top_k,
                filters=request.filters,
                min_score=request.min_score,
            )
        elif search_type == "lexical":
            evidence = await self.lexical_search(
                project_id=request.project_id,
                query=request.query,
                top_k=top_k,
                filters=request.filters,
                min_score=request.min_score,
            )
        else:
            # Default: hybrid
            evidence = await self.hybrid_search(
                project_id=request.project_id,
                query=request.query,
                top_k=top_k,
                filters=request.filters,
                min_score=request.min_score,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return RetrievalResult(
            query=request.query,
            project_id=request.project_id,
            evidence=evidence,
            total_found=len(evidence),
            search_type=search_type,
            execution_time_ms=round(elapsed_ms, 2),
        )

    async def semantic_search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: SearchFilter | None = None,
        min_score: float | None = None,
    ) -> list[EvidenceChunk]:
        """Perform semantic vector similarity search within a single project."""
        if not query or not query.strip():
            return []

        # Generate query vector & adapt dimension
        raw_vec = await asyncio.to_thread(self.provider.embed_query, query)
        adapted_vec = self.provider.adapt_dimension(raw_vec, self.target_dimension)

        results = await self.repository.search_similar_chunks(
            project_id=project_id,
            query_vector=adapted_vec,
            limit=top_k,
            filters=filters,
        )

        evidence: list[EvidenceChunk] = []
        for chunk, distance in results:
            score = max(0.0, 1.0 - (distance / 2.0))
            if min_score is not None and score < min_score:
                continue

            evidence.append(self._build_evidence_chunk(chunk, score, "semantic"))

        return evidence

    async def lexical_search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: SearchFilter | None = None,
        min_score: float | None = None,
    ) -> list[EvidenceChunk]:
        """Perform lexical keyword search within a single project."""
        if not query or not query.strip():
            return []

        results = await self.repository.search_lexical_chunks(
            project_id=project_id,
            query_text=query,
            limit=top_k,
            filters=filters,
        )

        evidence: list[EvidenceChunk] = []
        for chunk, score in results:
            if min_score is not None and score < min_score:
                continue
            evidence.append(self._build_evidence_chunk(chunk, score, "lexical"))

        return evidence

    async def hybrid_search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: SearchFilter | None = None,
        alpha: float | None = None,
        min_score: float | None = None,
    ) -> list[EvidenceChunk]:
        """Perform hybrid (vector + lexical) search within a single project."""
        if not query or not query.strip():
            return []

        raw_vec = await asyncio.to_thread(self.provider.embed_query, query)
        adapted_vec = self.provider.adapt_dimension(raw_vec, self.target_dimension)
        chosen_alpha = alpha if alpha is not None else self.hybrid_alpha

        results = await self.repository.search_hybrid_chunks(
            project_id=project_id,
            query_vector=adapted_vec,
            query_text=query,
            limit=top_k,
            filters=filters,
            alpha=chosen_alpha,
        )

        evidence: list[EvidenceChunk] = []
        for chunk, score, match_type in results:
            if min_score is not None and score < min_score:
                continue
            evidence.append(self._build_evidence_chunk(chunk, score, match_type))

        return evidence

    @staticmethod
    def _build_evidence_chunk(chunk: DBCodeChunk, score: float, match_type: str) -> EvidenceChunk:
        """Construct an EvidenceChunk model from a database CodeChunk."""
        file_path = "unknown"
        if getattr(chunk, "file", None) and getattr(chunk.file, "path", None):
            file_path = chunk.file.path
        elif isinstance(chunk.meta, dict) and "file_path" in chunk.meta:
            file_path = chunk.meta["file_path"]

        return EvidenceChunk(
            chunk_id=str(chunk.id),
            file_path=file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            chunk_content=chunk.content,
            score=round(score, 4),
            match_type=match_type,
            symbol=chunk.symbol_name,
            parent_name=chunk.class_name,
            metadata={
                **(chunk.meta or {}),
                "chunk_type": chunk.chunk_type,
                "function_name": chunk.function_name,
            },
        )
