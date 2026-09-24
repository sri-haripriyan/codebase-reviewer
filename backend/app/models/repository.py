"""Repository model representing Git or uploaded repository structure."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.file import File
    from backend.app.models.project import Project


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Repository metadata associated with an ingested project."""

    __tablename__ = "repositories"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent project ID for tenant isolation",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Repository name (e.g. owner/repo or folder name)",
    )
    default_branch: Mapped[str] = mapped_column(
        String(100),
        default="main",
        nullable=False,
        doc="Default branch (e.g. main, master)",
    )
    commit_sha: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Git commit SHA hash if available",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Structured repository metadata (stars, license, clone info, stats)",
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="repositories")
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Repository id={self.id} project_id={self.project_id} name='{self.name}'>"
