"""Repository for managing CodeChunk entities and pgvector similarity searches."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.code_chunk import CodeChunk
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
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.file_id == file_id,
            )
            .order_by(CodeChunk.start_line.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_similar_chunks(
        self,
        project_id: uuid.UUID,
        query_vector: list[float],
        limit: int = 10,
        distance_threshold: float | None = None,
    ) -> list[tuple[CodeChunk, float]]:
        """Perform cosine similarity search on embeddings strictly within the given project.

        Returns tuples of (CodeChunk, distance) ordered by closest distance.
        """
        # pgvector cosine distance operator: <=>
        distance = CodeChunk.embedding.cosine_distance(query_vector).label("distance")

        stmt = (
            select(CodeChunk, distance)
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )

        if distance_threshold is not None:
            stmt = stmt.where(distance <= distance_threshold)

        result = await self.session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

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
