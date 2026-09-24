"""Language-independent parsed code representation models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportStatement:
    """Represents an imported module or symbols within a source file."""

    module: str
    names: list[str] = field(default_factory=list)
    raw_statement: str = ""
    line_number: int = 1


@dataclass
class CodeElement:
    """Represents an AST symbol (function, method, class, interface, etc.)."""

    name: str
    element_type: str  # "class", "interface", "function", "method", "struct", "type_alias"
    start_line: int  # 1-indexed inclusive
    end_line: int  # 1-indexed inclusive
    parent_name: str | None = None
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    content: str = ""
    children: list["CodeElement"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        """Return the number of lines spanned by this element."""
        return max(1, self.end_line - self.start_line + 1)


@dataclass
class ParsedFile:
    """Top-level language-independent parsed representation of a source file."""

    file_path: str
    language: str
    imports: list[ImportStatement] = field(default_factory=list)
    elements: list[CodeElement] = field(default_factory=list)
    docstring: str | None = None
    errors: list[str] = field(default_factory=list)
    raw_code: str = ""
    total_lines: int = 0
    comments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
