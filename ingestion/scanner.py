"""Root ingestion.scanner module forwarding to backend.app.ingestion.scanner."""

from backend.app.ingestion.scanner import (
    DEFAULT_IGNORED_DIRS,
    DEFAULT_IGNORED_EXTENSIONS,
    EXTENSION_LANGUAGE_MAP,
    CodebaseScanner,
    calculate_file_hash,
    count_text_lines,
    detect_language,
    is_binary_file,
)

__all__ = [
    "DEFAULT_IGNORED_DIRS",
    "DEFAULT_IGNORED_EXTENSIONS",
    "EXTENSION_LANGUAGE_MAP",
    "CodebaseScanner",
    "calculate_file_hash",
    "count_text_lines",
    "detect_language",
    "is_binary_file",
]
