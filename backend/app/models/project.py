"""Project model representing an ingested codebase or analysis workspace."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.code_chunk import CodeChunk
    from backend.app.models.conversation import Conversation
    from backend.app.models.file import File
    from backend.app.models.report import Report
    from backend.app.models.repository import Repository


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level container for codebase analysis, reports, and conversations."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Human-readable unique project name",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Ingestion source type (e.g. github, zip, local)",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        doc="Remote GitHub URL or original source package location",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        index=True,
        nullable=False,
        doc="Project lifecycle status (created, ingesting, ready, error)",
    )

    # Relationships with cascade delete ensuring strict project isolation cleanup
    repositories: Mapped[list["Repository"]] = relationship(
        "Repository",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    code_chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("status", "created")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Project id={self.id} name='{self.name}' status='{self.status}'>"
