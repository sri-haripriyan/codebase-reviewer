"""Repository for CodeChunk entities, pgvector similarity searches, and hybrid retrieval."""

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.app.models.code_chunk import CodeChunk
from backend.app.models.file import File
from backend.app.repositories.base import BaseProjectScopedRepository


class CodeChunkRepository(BaseProjectScopedRepository[CodeChunk]):
    """Data access repository for code chunks and vector search."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CodeChunk, session)

    async def list_by_file(
        self,
        project_id: uuid.UUID,
        file_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CodeChunk]:
        """Fetch chunks for a specific file within a project."""
        stmt = (
            select(CodeChunk)
            .options(joinedload(CodeChunk.file))
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.file_id == file_id,
            )
            .order_by(CodeChunk.start_line.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    def _apply_filters(self, stmt: Any, filters: Any | None) -> Any:
        """Apply metadata filters to a query."""
        if not filters:
            return stmt

        if getattr(filters, "language", None):
            stmt = stmt.where(File.language == filters.language.lower())
        if getattr(filters, "file_path_pattern", None):
            stmt = stmt.where(File.path.ilike(f"%{filters.file_path_pattern}%"))
        if getattr(filters, "chunk_types", None):
            stmt = stmt.where(CodeChunk.chunk_type.in_(filters.chunk_types))
        if getattr(filters, "symbol_name", None):
            stmt = stmt.where(CodeChunk.symbol_name.ilike(f"%{filters.symbol_name}%"))

        return stmt

    async def search_similar_chunks(
        self,
        project_id: uuid.UUID,
        query_vector: list[float],
        limit: int = 10,
        distance_threshold: float | None = None,
        filters: Any | None = None,
    ) -> list[tuple[CodeChunk, float]]:
        """Perform cosine similarity search on embeddings strictly within the given project.

        Returns tuples of (CodeChunk, distance) ordered by closest distance.
        """
        distance = CodeChunk.embedding.cosine_distance(query_vector).label("distance")

        stmt = (
            select(CodeChunk, distance)
            .join(File, CodeChunk.file_id == File.id)
            .options(joinedload(CodeChunk.file))
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.embedding.is_not(None),
            )
        )

        stmt = self._apply_filters(stmt, filters)

        if distance_threshold is not None:
            stmt = stmt.where(distance <= distance_threshold)

        stmt = stmt.order_by(distance.asc()).limit(limit)

        result = await self.session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.unique().all()]

    async def search_lexical_chunks(
        self,
        project_id: uuid.UUID,
        query_text: str,
        limit: int = 10,
        filters: Any | None = None,
    ) -> list[tuple[CodeChunk, float]]:
        """Perform lexical keyword search on chunk content and symbol names."""
        terms = [t for t in re.findall(r"[A-Za-z0-9_]+", query_text.lower()) if len(t) >= 2]
        if not terms:
            return []

        # Build OR conditions for content and symbol_name
        conditions = []
        for t in terms:
            conditions.append(CodeChunk.content.ilike(f"%{t}%"))
            conditions.append(CodeChunk.symbol_name.ilike(f"%{t}%"))

        stmt = (
            select(CodeChunk)
            .join(File, CodeChunk.file_id == File.id)
            .options(joinedload(CodeChunk.file))
            .where(
                CodeChunk.project_id == project_id,
                or_(*conditions),
            )
        )

        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.limit(limit * 3)

        result = await self.session.execute(stmt)
        chunks = list(result.scalars().unique().all())

        # Score chunks based on term occurrences and exact symbol matches
        scored: list[tuple[CodeChunk, float]] = []
        for chunk in chunks:
            c_lower = chunk.content.lower()
            sym_lower = (chunk.symbol_name or "").lower()
            matches = sum(1 for t in terms if t in c_lower)
            symbol_boost = 1.0 if any(t in sym_lower for t in terms) else 0.0
            score = (matches / len(terms)) * 0.7 + symbol_boost * 0.3
            scored.append((chunk, min(1.0, score)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def search_hybrid_chunks(
        self,
        project_id: uuid.UUID,
        query_vector: list[float],
        query_text: str,
        limit: int = 10,
        distance_threshold: float | None = None,
        filters: Any | None = None,
        alpha: float = 0.7,
    ) -> list[tuple[CodeChunk, float, str]]:
        """Perform hybrid search combining vector similarity and lexical matching.

        Returns tuples of (CodeChunk, combined_score, match_type).
        """
        candidate_map: dict[uuid.UUID, tuple[CodeChunk, float, float]] = {}

        # 1. Semantic search
        semantic_results = await self.search_similar_chunks(
            project_id=project_id,
            query_vector=query_vector,
            limit=limit * 2,
            distance_threshold=distance_threshold,
            filters=filters,
        )

        for chunk, dist in semantic_results:
            sem_score = max(0.0, 1.0 - (dist / 2.0))
            candidate_map[chunk.id] = (chunk, sem_score, 0.0)

        # 2. Lexical search
        lexical_results = await self.search_lexical_chunks(
            project_id=project_id,
            query_text=query_text,
            limit=limit * 2,
            filters=filters,
        )

        for chunk, lex_score in lexical_results:
            if chunk.id in candidate_map:
                ch, s_score, _ = candidate_map[chunk.id]
                candidate_map[chunk.id] = (ch, s_score, lex_score)
            else:
                candidate_map[chunk.id] = (chunk, 0.0, lex_score)

        # 3. Combine scores
        fused: list[tuple[CodeChunk, float, str]] = []
        for chunk, s_score, l_score in candidate_map.values():
            if s_score > 0 and l_score > 0:
                match_type = "hybrid"
                combined = alpha * s_score + (1.0 - alpha) * l_score
            elif s_score > 0:
                match_type = "semantic"
                combined = s_score
            else:
                match_type = "lexical"
                combined = l_score * 0.8  # slightly discount pure lexical matches

            fused.append((chunk, combined, match_type))

        fused.sort(key=lambda x: x[1], reverse=True)
        return fused[:limit]

    async def bulk_create(
        self,
        project_id: uuid.UUID,
        chunks_data: list[dict[str, Any]],
    ) -> list[CodeChunk]:
        """Batch-insert code chunks for a project."""
        instances = [CodeChunk(project_id=project_id, **data) for data in chunks_data]
        self.session.add_all(instances)
        await self.session.flush()
        return instances

    async def count_by_file(self, project_id: uuid.UUID, file_id: uuid.UUID) -> int:
        """Count total chunks for a given file within a project."""
        stmt = (
            select(func.count())
            .select_from(CodeChunk)
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.file_id == file_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
