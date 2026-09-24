"""Unified ingestion pipeline coordinating source extraction, file scanning,
and database persistence.
"""

from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.ingestion.github import GitHubIngester
from backend.app.ingestion.models import IngestionResult, ProjectSource
from backend.app.ingestion.scanner import CodebaseScanner
from backend.app.ingestion.zip import ZipIngester
from backend.app.repositories import (
    FileRepository,
    ProjectRepository,
    RepositoryRepository,
)

logger = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates codebase ingestion, scanning, and database cataloging."""

    def __init__(
        self,
        session: AsyncSession,
        github_ingester: GitHubIngester | None = None,
        zip_ingester: ZipIngester | None = None,
        scanner: CodebaseScanner | None = None,
    ) -> None:
        self.session = session
        self.github_ingester = github_ingester or GitHubIngester()
        self.zip_ingester = zip_ingester or ZipIngester()
        self.scanner = scanner or CodebaseScanner()

        self.project_repo = ProjectRepository(session)
        self.repo_repo = RepositoryRepository(session)
        self.file_repo = FileRepository(session)

    async def ingest_github(
        self,
        url: str,
        custom_project_name: str | None = None,
    ) -> IngestionResult:
        """Ingest a remote GitHub repository into an isolated directory and catalog into DB."""
        logger.info("Starting GitHub ingestion for URL: %s", url)
        source = self.github_ingester.ingest(url, custom_name=custom_project_name)
        return await self._process_and_persist(source)

    async def ingest_zip(
        self,
        zip_source: Path | str | bytes | BinaryIO,
        project_name: str | None = None,
    ) -> IngestionResult:
        """Ingest a ZIP archive into an isolated directory and catalog into PostgreSQL."""
        logger.info("Starting ZIP ingestion for project: %s", project_name or "unnamed")
        source = self.zip_ingester.ingest(zip_source, project_name=project_name)
        return await self._process_and_persist(source)

    async def _process_and_persist(self, source: ProjectSource) -> IngestionResult:
        """Scan codebase files, persist records to PostgreSQL, and clean up temporary directory."""
        try:
            # 1. Scan directory with ignore rules and language detection
            scanned_files, duplicates = self.scanner.scan(source.extracted_path)
            total_size = sum(f.size_bytes for f in scanned_files)
            languages = dict(Counter(f.language for f in scanned_files))

            # 2. Persist project entity
            # Handle unique name collision by appending a suffix if needed
            existing_project = await self.project_repo.get_by_name(source.name)
            project_name = source.name
            if existing_project:
                import uuid

                project_name = f"{source.name}-{uuid.uuid4().hex[:6]}"

            project = await self.project_repo.create(
                name=project_name,
                source_type=source.source_type,
                source_url=source.source_url,
                status="ready",
            )

            # 3. Persist repository entity
            repo_meta: dict[str, Any] = {
                **source.metadata,
                "total_scanned_files": len(scanned_files),
                "total_size_bytes": total_size,
                "languages": languages,
                "duplicate_groups": len(duplicates),
            }

            repo = await self.repo_repo.create_for_project(
                project_id=project.id,
                name=project_name,
                default_branch=source.default_branch,
                commit_sha=source.commit_sha,
                meta=repo_meta,
            )

            # 4. Batch-persist files strictly scoped to project_id
            if scanned_files:
                files_data = [
                    {
                        "repository_id": repo.id,
                        "path": f.relative_path,
                        "language": f.language,
                        "size": f.size_bytes,
                        "hash": f.content_hash,
                    }
                    for f in scanned_files
                ]
                await self.file_repo.bulk_create(
                    project_id=project.id,
                    files_data=files_data,
                )

            await self.session.commit()

            logger.info(
                "Successfully ingested project '%s' (ID: %s) with %d files into database.",
                project.name,
                project.id,
                len(scanned_files),
            )

            return IngestionResult(
                project_id=project.id,
                repository_id=repo.id,
                project_name=project.name,
                source_type=source.source_type,
                source_url=source.source_url,
                total_files=len(scanned_files),
                total_size_bytes=total_size,
                languages=languages,
                duplicate_files_count=len(duplicates),
                commit_sha=source.commit_sha,
            )

        finally:
            # Guarantee workspace cleanup
            source.cleanup()
