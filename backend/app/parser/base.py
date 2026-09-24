"""Abstract base parser interface."""

from abc import ABC, abstractmethod

from backend.app.parser.models import ParsedFile


class BaseParser(ABC):
    """Abstract interface for source code parsers."""

    @abstractmethod
    def parse(self, code: str, file_path: str = "") -> ParsedFile:
        """Parse source code into a structured language-independent ParsedFile representation."""
        pass
