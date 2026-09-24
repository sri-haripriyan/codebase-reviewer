"""Base repository providing project-scoped CRUD operations for multi-tenant isolation."""

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.base import Base


class BaseProjectScopedRepository[ModelType: Base]:
    """Generic repository enforcing project_id filtering on all data access."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, project_id: uuid.UUID, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch a single entity strictly scoped to the specified project."""
        stmt = select(self.model).where(
            self.model.project_id == project_id,  # type: ignore[attr-defined]
            self.model.id == entity_id,  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """List entities belonging exclusively to the specified project."""
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id)  # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, project_id: uuid.UUID) -> int:
        """Count entities belonging exclusively to the specified project."""
        stmt = (
            select(func.count()).select_from(self.model).where(self.model.project_id == project_id)  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def create(self, project_id: uuid.UUID, **kwargs: Any) -> ModelType:
        """Create a new entity with guaranteed project_id binding."""
        kwargs["project_id"] = project_id
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(
        self,
        project_id: uuid.UUID,
        entity_id: uuid.UUID,
        **kwargs: Any,
    ) -> ModelType | None:
        """Update an existing entity scoped to project_id."""
        kwargs.pop("project_id", None)  # Prevent mutating project ownership
        stmt = (
            update(self.model)
            .where(
                self.model.project_id == project_id,  # type: ignore[attr-defined]
                self.model.id == entity_id,  # type: ignore[attr-defined]
            )
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, project_id: uuid.UUID, entity_id: uuid.UUID) -> bool:
        """Delete an entity strictly scoped to project_id."""
        stmt = delete(self.model).where(
            self.model.project_id == project_id,  # type: ignore[attr-defined]
            self.model.id == entity_id,  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)
