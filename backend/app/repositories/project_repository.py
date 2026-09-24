"""Repository for managing Project workspace entities."""

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.project import Project


class ProjectRepository:
    """Data access repository for projects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        """Fetch project by UUID."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Project | None:
        """Fetch project by unique name."""
        stmt = select(Project).where(Project.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[Project]:
        """List projects with optional status filter."""
        stmt = select(Project)
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, status: str | None = None) -> int:
        """Count total projects."""
        stmt = select(func.count()).select_from(Project)
        if status:
            stmt = stmt.where(Project.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def create(
        self,
        name: str,
        source_type: str,
        source_url: str | None = None,
        status: str = "created",
    ) -> Project:
        """Create and persist a new Project."""
        project = Project(
            name=name,
            source_type=source_type,
            source_url=source_url,
            status=status,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def update(self, project_id: uuid.UUID, **kwargs: Any) -> Project | None:
        """Update fields on a Project."""
        stmt = update(Project).where(Project.id == project_id).values(**kwargs).returning(Project)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, project_id: uuid.UUID, status: str) -> Project | None:
        """Update project status."""
        return await self.update(project_id, status=status)

    async def delete(self, project_id: uuid.UUID) -> bool:
        """Delete project and trigger cascade cleanup."""
        stmt = delete(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)
