"""Repository for managing Repository metadata entities."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.repository import Repository
from backend.app.repositories.base import BaseProjectScopedRepository


class RepositoryRepository(BaseProjectScopedRepository[Repository]):
    """Data access repository for Git/source repositories."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Repository, session)

    async def get_by_project(self, project_id: uuid.UUID) -> Repository | None:
        """Fetch the repository associated with a project."""
        stmt = select(Repository).where(Repository.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_for_project(
        self,
        project_id: uuid.UUID,
        name: str,
        default_branch: str = "main",
        commit_sha: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Repository:
        """Create a new Repository record bound to the specified project."""
        return await self.create(
            project_id=project_id,
            name=name,
            default_branch=default_branch,
            commit_sha=commit_sha,
            meta=meta or {},
        )
