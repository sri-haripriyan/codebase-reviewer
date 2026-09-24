"""Root ingestion package alias pointing to backend.app.ingestion."""

from backend.app.ingestion.github import GitHubIngester, validate_github_url
from backend.app.ingestion.models import IngestionResult, ProjectSource, ScannedFile
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.ingestion.scanner import CodebaseScanner
from backend.app.ingestion.zip import ZipIngester

__all__ = [
    "CodebaseScanner",
    "GitHubIngester",
    "IngestionPipeline",
    "IngestionResult",
    "ProjectSource",
    "ScannedFile",
    "ZipIngester",
    "validate_github_url",
]
