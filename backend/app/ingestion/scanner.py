"""Codebase scanner for recursive file discovery, filtering, and metadata extraction."""

import hashlib
import os
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from backend.app.core.logging import get_logger
from backend.app.ingestion.models import ScannedFile

logger = get_logger(__name__)

# Default directories excluded from codebase analysis
DEFAULT_IGNORED_DIRS: set[str] = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Package & dependency caches
    "node_modules",
    "bower_components",
    "vendor",
    # Python & runtime environments
    ".venv",
    "venv",
    "env",
    ".env",
    "virtualenv",
    ".tox",
    ".nox",
    # Build artifacts & compilation targets
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    ".next",
    ".nuxt",
    ".turbo",
    ".gradle",
    # Tooling & IDE caches
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".coverage",
    "htmlcov",
    ".idea",
    ".vscode",
    ".vs",
}

# Default file extensions excluded from source code analysis
DEFAULT_IGNORED_EXTENSIONS: set[str] = {
    # Compiled binaries & bytecode
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".pyc",
    ".pyo",
    ".pyd",
    ".class",
    ".jar",
    ".war",
    # Archives & compressed formats
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".bz2",
    ".xz",
    # Images, video, audio
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".bmp",
    ".tiff",
    ".webp",
    ".svg",
    ".mp4",
    ".mp3",
    ".wav",
    ".ogg",
    ".avi",
    ".mov",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    # Data blobs & databases
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".arrow",
    # Source maps & minified web artifacts
    ".map",
    ".min.js",
    ".min.css",
    ".lock",
}

# Well-known exact filenames mapped to language types
WELL_KNOWN_FILENAMES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "jenkinsfile": "groovy",
    "vagrantfile": "ruby",
    "gemfile": "ruby",
    "rakefile": "ruby",
}

# Common file extension to programming language mappings
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".bat": "batch",
    ".cmd": "batch",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".less": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
}


def is_binary_file(path: Path) -> bool:
    """Check if a file appears to be binary by scanning the first 8 KB for null bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        return True


def calculate_file_hash(path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(64 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_text_lines(path: Path) -> int:
    """Safely count the number of lines in a text file."""
    try:
        count = 0
        with open(path, "rb") as f:
            for line in f:
                count += 1
        return count
    except OSError:
        return 0


def detect_language(path: Path) -> str:
    """Detect programming or markup language from filename or extension."""
    name_lower = path.name.lower()
    if name_lower in WELL_KNOWN_FILENAMES:
        return WELL_KNOWN_FILENAMES[name_lower]

    suffix = path.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(suffix, "unknown")


class CodebaseScanner:
    """Recursively scans codebase directories and catalogs files with configurable ignore rules."""

    def __init__(
        self,
        ignored_dirs: Sequence[str] | None = None,
        ignored_extensions: Sequence[str] | None = None,
        skip_binary_check: bool = False,
    ) -> None:
        self.ignored_dirs: set[str] = (
            set(ignored_dirs) if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
        )
        self.ignored_extensions: set[str] = (
            set(ignored_extensions)
            if ignored_extensions is not None
            else DEFAULT_IGNORED_EXTENSIONS
        )
        self.skip_binary_check = skip_binary_check

    def scan(self, root_dir: Path) -> tuple[list[ScannedFile], dict[str, list[str]]]:
        """Scan directory and return discovered files along with detected duplicates.

        Returns:
            - list of ScannedFile instances
            - dict mapping content_hash -> list of duplicate relative paths
        """
        root_dir = root_dir.resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            raise ValueError(f"Scan target is not a valid directory: {root_dir}")

        scanned_files: list[ScannedFile] = []
        files_by_hash: dict[str, list[str]] = defaultdict(list)

        for root, dirs, files in os.walk(root_dir):
            # Prune ignored directories in-place to avoid recursing into them
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs and not d.startswith(".")]

            for file_name in files:
                file_path = Path(root) / file_name

                # Skip files with ignored extensions
                file_lower = file_name.lower()
                if any(file_lower.endswith(ext) for ext in self.ignored_extensions):
                    continue

                try:
                    size = file_path.stat().st_size
                except OSError:
                    continue

                # Skip empty files or files that are confirmed binary
                if not self.skip_binary_check and is_binary_file(file_path):
                    continue

                # Calculate relative POSIX path
                rel_path = file_path.relative_to(root_dir).as_posix()
                content_hash = calculate_file_hash(file_path)
                language = detect_language(file_path)
                lines = count_text_lines(file_path)

                scanned_file = ScannedFile(
                    relative_path=rel_path,
                    absolute_path=file_path,
                    language=language,
                    size_bytes=size,
                    content_hash=content_hash,
                    line_count=lines,
                )
                scanned_files.append(scanned_file)
                files_by_hash[content_hash].append(rel_path)

        # Filter duplicates: keep only hashes with > 1 occurrences
        duplicates = {h: paths for h, paths in files_by_hash.items() if len(paths) > 1}

        logger.info(
            "Scanned %d files in %s (found %d duplicate groups)",
            len(scanned_files),
            root_dir,
            len(duplicates),
        )

        return scanned_files, duplicates
