"""Root ingestion.github module forwarding to backend.app.ingestion.github."""

from backend.app.ingestion.github import GitHubIngester, validate_github_url

__all__ = ["GitHubIngester", "validate_github_url"]
