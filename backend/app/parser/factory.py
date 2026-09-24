"""Parser factory resolving the appropriate parser for a given programming language."""

from backend.app.core.logging import get_logger
from backend.app.parser.base import BaseParser
from backend.app.parser.fallback_parser import FallbackParser
from backend.app.parser.models import ParsedFile
from backend.app.parser.tree_sitter_parser import TreeSitterParser

logger = get_logger(__name__)

# Map common language names / extensions to Tree-sitter identifiers
_TREE_SITTER_LANGUAGE_MAP: dict[str, str] = {
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "jsx": "jsx",
    "mjs": "javascript",
    "cjs": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "tsx",
    "java": "java",
    "csharp": "csharp",
    "c#": "csharp",
    "cs": "csharp",
    "go": "go",
    "golang": "go",
}


def get_parser_for_language(language: str) -> BaseParser:
    """Return a TreeSitterParser if supported, otherwise return a FallbackParser."""
    normalized = language.strip().lower()
    ts_lang = _TREE_SITTER_LANGUAGE_MAP.get(normalized)

    if ts_lang:
        try:
            return TreeSitterParser(ts_lang)
        except Exception as e:
            logger.warning(
                "Failed to initialize TreeSitterParser for %s (%s). Falling back: %s",
                language,
                ts_lang,
                e,
            )

    return FallbackParser(language=normalized or "generic")


def parse_source_code(code: str, language: str, file_path: str = "") -> ParsedFile:
    """Parse source code with the appropriate parser, guaranteeing a ParsedFile result."""
    parser = get_parser_for_language(language)
    try:
        return parser.parse(code, file_path=file_path)
    except Exception as e:
        logger.warning(
            "Parser %s failed on %s (%s), falling back to heuristic parser: %s",
            type(parser).__name__,
            file_path,
            language,
            e,
        )
        return FallbackParser(language=language).parse(code, file_path=file_path)
