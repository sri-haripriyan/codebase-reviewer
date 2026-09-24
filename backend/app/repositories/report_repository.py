"""Repository for managing structured analysis Reports and review lifecycles."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.report import Report
from backend.app.repositories.base import BaseProjectScopedRepository


class ReportRepository(BaseProjectScopedRepository[Report]):
    """Data access repository for codebase reports, versioning, and human review status."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Report, session)

    async def get_latest_report(self, project_id: uuid.UUID) -> Report | None:
        """Fetch the most recent report version for a project."""
        stmt = (
            select(Report)
            .where(Report.project_id == project_id)
            .order_by(Report.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_version(self, project_id: uuid.UUID, version: int) -> Report | None:
        """Fetch a specific report version for a project."""
        stmt = select(Report).where(
            Report.project_id == project_id,
            Report.version == version,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_version_number(self, project_id: uuid.UUID) -> int:
        """Calculate the next version number for a project report."""
        stmt = select(func.max(Report.version)).where(Report.project_id == project_id)
        result = await self.session.execute(stmt)
        max_ver = result.scalar_one_or_none()
        return (max_ver or 0) + 1

    async def create_report(
        self,
        project_id: uuid.UUID,
        title: str,
        content_json: dict[str, Any],
        status: str = "draft",
        feedback: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Report:
        """Create a new report version bound to a project."""
        next_ver = await self.get_next_version_number(project_id)
        return await self.create(
            project_id=project_id,
            title=title,
            version=next_ver,
            status=status,
            content_json=content_json,
            feedback=feedback,
            meta=meta or {},
        )

    async def update_review_status(
        self,
        project_id: uuid.UUID,
        report_id: uuid.UUID,
        status: str,
        feedback: str | None = None,
        approved: bool = False,
    ) -> Report | None:
        """Update report review status, feedback, and approval timestamp."""
        updates: dict[str, Any] = {"status": status}
        if feedback is not None:
            updates["feedback"] = feedback
        if approved:
            updates["approved_at"] = datetime.now(UTC)
        return await self.update(project_id, report_id, **updates)

    async def list_versions(self, project_id: uuid.UUID) -> list[Report]:
        """List all versions of reports for a project ordered by version descending."""
        stmt = select(Report).where(Report.project_id == project_id).order_by(Report.version.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
