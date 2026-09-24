"""Data structures representing ingested project sources and scanned file metadata."""

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProjectSource:
    """Unified internal representation of an ingested codebase source."""

    source_type: str  # "github" or "zip"
    name: str
    extracted_path: Path
    source_url: str | None = None
    default_branch: str = "main"
    commit_sha: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def cleanup(self) -> None:
        """Safely clean up temporary workspace files."""
        if self.extracted_path and self.extracted_path.exists():
            shutil.rmtree(self.extracted_path, ignore_errors=True)

    def __enter__(self) -> "ProjectSource":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()


@dataclass
class ScannedFile:
    """Metadata of an individual source code file discovered by scanner."""

    relative_path: str  # POSIX relative path, e.g. "src/app.py"
    absolute_path: Path
    language: str
    size_bytes: int
    content_hash: str  # SHA-256
    line_count: int = 0


@dataclass
class IngestionResult:
    """Summary deliverable produced upon successful project ingestion."""

    project_id: uuid.UUID
    repository_id: uuid.UUID
    project_name: str
    source_type: str
    source_url: str | None
    total_files: int
    total_size_bytes: int
    languages: dict[str, int]
    duplicate_files_count: int
    commit_sha: str | None = None
