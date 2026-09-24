"""Repository for managing File entities with strict project isolation."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.file import File
from backend.app.repositories.base import BaseProjectScopedRepository


class FileRepository(BaseProjectScopedRepository[File]):
    """Data access repository for project source files."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(File, session)

    async def get_by_path(self, project_id: uuid.UUID, path: str) -> File | None:
        """Fetch a specific file by its relative path within a project."""
        stmt = select(File).where(
            File.project_id == project_id,
            File.path == path,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_hash(self, project_id: uuid.UUID, file_hash: str) -> list[File]:
        """Fetch files matching content hash within a project."""
        stmt = select(File).where(
            File.project_id == project_id,
            File.hash == file_hash,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_language(
        self,
        project_id: uuid.UUID,
        language: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[File]:
        """List files of a given programming language within a project."""
        stmt = (
            select(File)
            .where(
                File.project_id == project_id,
                File.language == language.lower(),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(
        self,
        project_id: uuid.UUID,
        files_data: list[dict[str, Any]],
    ) -> list[File]:
        """Batch-insert files belonging to a project."""
        instances = [File(project_id=project_id, **data) for data in files_data]
        self.session.add_all(instances)
        await self.session.flush()
        return instances
