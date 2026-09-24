"""Initial schema with projects, repositories, files, code_chunks,
conversations, messages, and reports.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-09-23 14:30:00.000000

"""

from collections.abc import Sequence

import pgvector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Ensure pgvector extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create projects table
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)
    op.create_index("ix_projects_status", "projects", ["status"], unique=False)

    # 3. Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=100), server_default="main", nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("meta", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"], unique=False)
    op.create_index("ix_repositories_commit_sha", "repositories", ["commit_sha"], unique=False)

    # 4. Create files table
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("language", sa.String(length=100), server_default="unknown", nullable=False),
        sa.Column("size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_files_project_id", "files", ["project_id"], unique=False)
    op.create_index("ix_files_repository_id", "files", ["repository_id"], unique=False)
    op.create_index("ix_files_path", "files", ["path"], unique=False)
    op.create_index("ix_files_language", "files", ["language"], unique=False)
    op.create_index("ix_files_hash", "files", ["hash"], unique=False)
    op.create_index("ix_files_project_id_path", "files", ["project_id", "path"], unique=True)
    op.create_index("ix_files_project_id_hash", "files", ["project_id", "hash"], unique=False)

    # 5. Create code_chunks table with pgvector embedding
    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=50), server_default="block", nullable=False),
        sa.Column("symbol_name", sa.String(length=255), nullable=True),
        sa.Column("class_name", sa.String(length=255), nullable=True),
        sa.Column("function_name", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_code_chunks_project_id", "code_chunks", ["project_id"], unique=False)
    op.create_index("ix_code_chunks_file_id", "code_chunks", ["file_id"], unique=False)
    op.create_index("ix_code_chunks_chunk_type", "code_chunks", ["chunk_type"], unique=False)
    op.create_index("ix_code_chunks_symbol_name", "code_chunks", ["symbol_name"], unique=False)
    op.create_index(
        "ix_code_chunks_project_file", "code_chunks", ["project_id", "file_id"], unique=False
    )
    op.create_index(
        "ix_code_chunks_project_type", "code_chunks", ["project_id", "chunk_type"], unique=False
    )
    # HNSW vector index using cosine distance
    op.create_index(
        "ix_code_chunks_embedding_hnsw",
        "code_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # 6. Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title", sa.String(length=255), server_default="New Conversation", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"], unique=False)

    # 7. Create messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_project_id", "messages", ["project_id"], unique=False)
    op.create_index(
        "ix_messages_project_conversation",
        "messages",
        ["project_id", "conversation_id"],
        unique=False,
    )

    # 8. Create reports table
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            server_default="Codebase Analysis Report",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_reports_project_id", "reports", ["project_id"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)
    op.create_index("ix_reports_project_status", "reports", ["project_id", "status"], unique=False)
    op.create_index(
        "ix_reports_project_version", "reports", ["project_id", "version"], unique=False
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("code_chunks")
    op.drop_table("files")
    op.drop_table("repositories")
    op.drop_table("projects")
