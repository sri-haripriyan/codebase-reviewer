"""Data models for code chunks produced by chunkers."""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeChunk:
    """A semantic chunk of code optimized for retrieval and context preservation."""

    file_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'module_header', 'function', 'method', 'class_header', 'generic', etc.
    symbol_name: str | None = None
    parent_name: str | None = None
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        """Return the number of lines in this chunk."""
        return max(1, self.end_line - self.start_line + 1)
