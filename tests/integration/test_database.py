"""Integration tests for PostgreSQL, pgvector embedding storage, and similarity search."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.repositories import (
    CodeChunkRepository,
    FileRepository,
    ProjectRepository,
    RepositoryRepository,
)


@pytest.mark.asyncio
async def test_database_tables_exist(db_session: AsyncSession):
    """Verify that all required tables and the pgvector extension exist in PostgreSQL."""
    # Check extension
    ext_result = await db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    )
    assert ext_result.scalar_one_or_none() == "vector"

    # Check tables
    tables_result = await db_session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
        )
    )
    existing_tables = {row[0] for row in tables_result.fetchall()}
    expected_tables = {
        "alembic_version",
        "projects",
        "repositories",
        "files",
        "code_chunks",
        "conversations",
        "messages",
        "reports",
    }
    assert expected_tables.issubset(existing_tables)


@pytest.mark.asyncio
async def test_pgvector_embedding_similarity_search(db_session: AsyncSession):
    """Verify storing vector embeddings and querying nearest neighbors via cosine distance."""
    proj_repo = ProjectRepository(db_session)
    repo_repo = RepositoryRepository(db_session)
    file_repo = FileRepository(db_session)
    chunk_repo = CodeChunkRepository(db_session)

    dim = settings.EMBEDDING_DIMENSION
    proj = await proj_repo.create(
        name=f"vector-search-test-{uuid.uuid4().hex[:8]}",
        source_type="github",
    )

    try:
        git_repo = await repo_repo.create_for_project(
            project_id=proj.id,
            name="vector/demo",
        )
        test_file = await file_repo.create(
            project_id=proj.id,
            repository_id=git_repo.id,
            path="core/auth.py",
            language="python",
            size=256,
            hash="vec_hash_1",
        )

        # Create two distinct unit vectors
        # Vector 1: oriented toward dimension 0
        vec_auth = [0.0] * dim
        vec_auth[0] = 1.0

        # Vector 2: oriented toward dimension 1
        vec_db = [0.0] * dim
        vec_db[1] = 1.0

        chunk_auth = await chunk_repo.create(
            project_id=proj.id,
            file_id=test_file.id,
            content="def authenticate_user(token: str): ...",
            start_line=1,
            end_line=5,
            chunk_type="function",
            symbol_name="authenticate_user",
            embedding=vec_auth,
        )

        chunk_db = await chunk_repo.create(
            project_id=proj.id,
            file_id=test_file.id,
            content="def get_database_connection(): ...",
            start_line=7,
            end_line=12,
            chunk_type="function",
            symbol_name="get_database_connection",
            embedding=vec_db,
        )

        # Query with vector very close to Vector 1 (auth)
        query_vec = [0.0] * dim
        query_vec[0] = 0.95
        query_vec[2] = 0.05

        results = await chunk_repo.search_similar_chunks(
            project_id=proj.id,
            query_vector=query_vec,
            limit=2,
        )

        assert len(results) == 2
        top_chunk, distance = results[0]
        # Closest match must be chunk_auth
        assert top_chunk.id == chunk_auth.id
        assert top_chunk.symbol_name == "authenticate_user"
        assert distance < 0.1  # Very small cosine distance

        second_chunk, second_dist = results[1]
        assert second_chunk.id == chunk_db.id
        assert second_dist > distance

    finally:
        # Cascade cleanup
        await proj_repo.delete(proj.id)
