"""Code chunk model representing AST/semantic code segments and their vector embeddings."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.config import settings
from backend.app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from backend.app.models.file import File
    from backend.app.models.project import Project


class CodeChunk(Base, UUIDPrimaryKeyMixin):
    """Segmented block of code with syntax metadata and pgvector embedding."""

    __tablename__ = "code_chunks"

    __table_args__ = (
        Index("ix_code_chunks_project_file", "project_id", "file_id"),
        Index("ix_code_chunks_project_type", "project_id", "chunk_type"),
        Index("ix_code_chunks_symbol_name", "symbol_name"),
        # HNSW vector index using cosine distance (vector_cosine_ops)
        Index(
            "ix_code_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Project ID for strict multi-tenant isolation",
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Parent file ID",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Raw text / source code of this chunk",
    )
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-indexed starting line number",
    )
    end_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-indexed ending line number",
    )
    chunk_type: Mapped[str] = mapped_column(
        String(50),
        default="block",
        index=True,
        nullable=False,
        doc="Syntax segment type (e.g. function, class, module, block)",
    )
    symbol_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Primary symbol name defined by this chunk (if any)",
    )
    class_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Enclosing class name (if applicable)",
    )
    function_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Enclosing or defined function name (if applicable)",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="AST metadata, imports, dependencies, token count, and docstrings",
    )
    # Embedding vector with configurable dimension from settings.EMBEDDING_DIMENSION
    # (Default 1536 matches standard OpenAI text-embedding-3-small or similar embedding models)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
        doc=f"Dense vector embedding (dim={settings.EMBEDDING_DIMENSION})",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        doc="Chunk generation timestamp (timezone-aware UTC)",
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="code_chunks")
    file: Mapped["File"] = relationship("File", back_populates="code_chunks")

    def __repr__(self) -> str:
        return (
            f"<CodeChunk id={self.id} project_id={self.project_id} "
            f"type='{self.chunk_type}' symbol='{self.symbol_name}'>"
        )
