"""Report model representing structured analysis deliverables and human review lifecycle."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.project import Project


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured codebase report supporting human-in-the-loop review and versioning."""

    __tablename__ = "reports"

    __table_args__ = (
        Index("ix_reports_project_status", "project_id", "status"),
        Index("ix_reports_project_version", "project_id", "version"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent project ID for tenant isolation",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="Codebase Analysis Report",
        nullable=False,
        doc="Report title or executive summary headline",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        index=True,
        nullable=False,
        doc="Review status: draft, pending_review, approved, rejected, finalized",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        doc="Monotonically incrementing report version number",
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Structured report body (sections, architecture, security, metrics, diagrams)",
    )
    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human reviewer feedback provided during the review gate",
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when human review approval was granted",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Version metadata: agent run ID, export paths, token metrics",
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="reports")

    def __repr__(self) -> str:
        return (
            f"<Report id={self.id} project_id={self.project_id} "
            f"v{self.version} status='{self.status}'>"
        )
