"""GitHub repository ingestion module with security validation and shallow cloning."""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.models import ProjectSource

logger = get_logger(__name__)

# Pattern for GitHub owner and repo names: alphanumeric, hyphens, underscores, dots
_GITHUB_IDENTIFIER = r"^[a-zA-Z0-9_\-\.]+$"
_DISALLOWED_CHARS = set(";&|`$<>\"'\n\r\t \x00")


def validate_github_url(url: str) -> dict[str, str]:
    """Validate a GitHub repository URL and extract owner and repo name.

    Raises ValueError if the URL is invalid, insecure, or does not point to GitHub.
    """
    if not url or not isinstance(url, str):
        raise ValueError("GitHub URL must be a non-empty string.")

    url = url.strip()

    # Reject dangerous metacharacters to prevent command injection
    if any(char in url for char in _DISALLOWED_CHARS):
        raise ValueError("GitHub URL contains illegal characters or whitespace.")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Malformed URL: {e}") from e

    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https scheme.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in ("github.com", "www.github.com"):
        raise ValueError("Only github.com URLs are supported.")

    # Path should be /<owner>/<repo> (ignoring trailing .git or slashes)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError("URL must include both organization/user and repository name.")

    owner, repo = path_parts[0], path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not re.match(_GITHUB_IDENTIFIER, owner) or not re.match(_GITHUB_IDENTIFIER, repo):
        raise ValueError("Invalid owner or repository name in GitHub URL.")

    clean_url = f"https://github.com/{owner}/{repo}.git"
    return {
        "owner": owner,
        "repo": repo,
        "clean_url": clean_url,
        "name": f"{owner}/{repo}",
    }


class GitHubIngester:
    """Clones and extracts metadata from a remote GitHub repository into an isolated directory."""

    def __init__(
        self,
        timeout_seconds: int | None = None,
        max_size_bytes: int | None = None,
        temp_dir: Path | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds or settings.GITHUB_CLONE_TIMEOUT_SECONDS
        self.max_size_bytes = max_size_bytes or settings.MAX_EXTRACTED_SIZE_BYTES
        self.temp_root = temp_dir or (
            Path(settings.TEMP_WORKSPACE_DIR) if settings.TEMP_WORKSPACE_DIR else None
        )

    def ingest(self, url: str, custom_name: str | None = None) -> ProjectSource:
        """Validate, clone, and catalog a GitHub repository into an isolated workspace."""
        validated = validate_github_url(url)
        clean_url = validated["clean_url"]
        project_name = custom_name or validated["repo"]

        # Create isolated temporary workspace
        target_dir = Path(tempfile.mkdtemp(prefix="ingest_gh_", dir=self.temp_root)).resolve()

        try:
            logger.info("Cloning GitHub repository %s into %s", clean_url, target_dir)
            self._clone_repo(clean_url, target_dir)
            commit_sha = self._extract_commit_sha(target_dir)
            default_branch = self._extract_default_branch(target_dir)
            total_size = self._calculate_dir_size(target_dir)

            if total_size > self.max_size_bytes:
                mb_size = total_size / (1024 * 1024)
                max_mb = self.max_size_bytes / (1024 * 1024)
                raise ValueError(
                    f"Repository size ({mb_size:.1f} MB) exceeds limit ({max_mb:.1f} MB)."
                )

            metadata: dict[str, Any] = {
                "owner": validated["owner"],
                "repo": validated["repo"],
                "clean_url": clean_url,
                "size_bytes": total_size,
            }

            return ProjectSource(
                source_type="github",
                name=project_name,
                extracted_path=target_dir,
                source_url=clean_url,
                default_branch=default_branch,
                commit_sha=commit_sha,
                metadata=metadata,
            )

        except Exception:
            # Guarantee cleanup on failure
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

    def _clone_repo(self, clean_url: str, target_dir: Path) -> None:
        """Run shallow git clone with security flags and timeout."""
        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--no-tags",
            "--single-branch",
            "-c",
            "core.hooksPath=/dev/null",  # Never execute repository hooks
            clean_url,
            str(target_dir),
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if res.returncode != 0:
                raise RuntimeError(f"Git clone failed: {res.stderr.strip() or res.stdout.strip()}")
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Git clone timed out after {self.timeout_seconds} seconds.") from e

    def _extract_commit_sha(self, target_dir: Path) -> str | None:
        """Read current commit SHA without executing repo scripts."""
        try:
            res = subprocess.run(
                ["git", "-C", str(target_dir), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass

        # Fallback: direct read from .git/HEAD
        try:
            head_file = target_dir / ".git" / "HEAD"
            if head_file.exists():
                ref = head_file.read_text(encoding="utf-8").strip()
                if ref.startswith("ref: "):
                    ref_path = target_dir / ".git" / ref[5:]
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()
                elif len(ref) == 40:
                    return ref
        except Exception:
            pass
        return None

    def _extract_default_branch(self, target_dir: Path) -> str:
        """Read default branch name from cloned repo."""
        try:
            res = subprocess.run(
                ["git", "-C", str(target_dir), "symbolic-ref", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "main"

    def _calculate_dir_size(self, target_dir: Path) -> int:
        """Calculate total size in bytes of files in target directory."""
        total = 0
        for root, _, files in os.walk(target_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total
