"""Integration tests for end-to-end codebase ingestion pipeline and PostgreSQL persistence."""

import io
import uuid
import zipfile

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.models.repository import Repository
from backend.app.repositories import FileRepository, ProjectRepository


def build_sample_project_zip() -> bytes:
    """Create a sample zip project with source code and documentation."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("src/server.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        zf.writestr("src/models.py", "class User:\n    pass\n")
        zf.writestr("web/index.html", "<!DOCTYPE html><html><body>Hello</body></html>")
        zf.writestr("web/styles.css", "body { background: #000; }")
        zf.writestr("README.md", "# Sample FastApp\nA sample microservice.\n")
        # Add duplicate file
        zf.writestr("src/server_backup.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_ingest_zip_pipeline_end_to_end(db_session: AsyncSession):
    """Verify that a ZIP archive is ingested, scanned, persisted into PostgreSQL, and cleaned up."""
    zip_bytes = build_sample_project_zip()
    pipeline = IngestionPipeline(db_session)
    project_name = f"full-pipeline-test-{uuid.uuid4().hex[:6]}"

    result = await pipeline.ingest_zip(zip_bytes, project_name=project_name)

    try:
        # 1. Verify IngestionResult
        assert result.project_id is not None
        assert result.repository_id is not None
        assert result.project_name == project_name
        assert result.source_type == "zip"
        assert result.total_files == 6
        assert result.languages.get("python") == 3
        assert result.languages.get("html") == 1
        assert result.languages.get("css") == 1
        assert result.languages.get("markdown") == 1
        assert result.duplicate_files_count == 1  # server.py and server_backup.py

        # 2. Verify records in PostgreSQL
        proj_repo = ProjectRepository(db_session)
        file_repo = FileRepository(db_session)

        project = await proj_repo.get_by_id(result.project_id)
        assert project is not None
        assert project.status == "ready"
        assert project.source_type == "zip"

        # Verify repository entity
        repo_stmt = select(Repository).where(Repository.id == result.repository_id)
        repo_res = await db_session.execute(repo_stmt)
        repo = repo_res.scalar_one_or_none()
        assert repo is not None
        assert repo.project_id == project.id
        assert repo.meta["total_scanned_files"] == 6

        # Verify persisted files
        db_files = await file_repo.list(project.id, limit=20)
        assert len(db_files) == 6
        file_paths = {f.path for f in db_files}
        assert "src/server.py" in file_paths
        assert "web/index.html" in file_paths
        assert "README.md" in file_paths

        # Verify project isolation: random other project_id yields 0 files
        other_project_id = uuid.uuid4()
        other_files = await file_repo.list(other_project_id)
        assert len(other_files) == 0

    finally:
        # Cleanup test project
        await proj_repo.delete(result.project_id)
        await db_session.commit()
