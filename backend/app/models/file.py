"""File model representing an individual source file within an ingested repository."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from backend.app.models.code_chunk import CodeChunk
    from backend.app.models.project import Project
    from backend.app.models.repository import Repository


class File(Base, UUIDPrimaryKeyMixin):
    """File inventory entity belonging to a project and repository."""

    __tablename__ = "files"

    __table_args__ = (
        Index("ix_files_project_id_path", "project_id", "path", unique=True),
        Index("ix_files_project_id_hash", "project_id", "hash"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Project ID for strict multi-tenant isolation",
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent repository ID",
    )
    path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Relative path of the file in the repository",
    )
    language: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        index=True,
        nullable=False,
        doc="Detected programming language",
    )
    size: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="File size in bytes",
    )
    hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 content hash for change detection & deduplication",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        doc="File cataloging timestamp (timezone-aware UTC)",
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="files")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")
    code_chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<File id={self.id} project_id={self.project_id} path='{self.path}'>"
