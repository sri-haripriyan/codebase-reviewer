"""Root parser package alias pointing to backend.app.parser."""

from backend.app.parser.base import BaseParser
from backend.app.parser.factory import get_parser_for_language, parse_source_code
from backend.app.parser.fallback_parser import FallbackParser
from backend.app.parser.models import CodeElement, ImportStatement, ParsedFile
from backend.app.parser.tree_sitter_parser import TreeSitterParser

__all__ = [
    "BaseParser",
    "CodeElement",
    "FallbackParser",
    "ImportStatement",
    "ParsedFile",
    "TreeSitterParser",
    "get_parser_for_language",
    "parse_source_code",
]
