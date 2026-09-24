"""Fallback heuristic parser for unsupported languages or when Tree-sitter fails."""

import re

from backend.app.core.logging import get_logger
from backend.app.parser.base import BaseParser
from backend.app.parser.models import CodeElement, ImportStatement, ParsedFile

logger = get_logger(__name__)

# Heuristic patterns for common languages
_IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import\s+([^\n]+)|import\s+([^\n]+))"),
    re.compile(r"^\s*import\s+(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"^\s*(?:using|#include)\s+([^\n;]+)"),
]

_CLASS_PATTERN = re.compile(
    r"^\s*(?:public\s+|private\s+|protected\s+|export\s+)*(?:class|struct|interface)\s+([A-Za-z_][A-Za-z0-9_]*)"
)

_FUNC_PATTERN = re.compile(
    r"^\s*(?:async\s+)?(?:def|function|func|fn|sub)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
)


class FallbackParser(BaseParser):
    """Heuristic regex-based parser that provides best-effort parsing for any language."""

    def __init__(self, language: str = "generic") -> None:
        self.language = language.lower()

    def parse(self, code: str, file_path: str = "") -> ParsedFile:
        """Parse source code using regex heuristics. Always succeeds without raising."""
        lines = code.splitlines(keepends=True)
        total_lines = len(lines)
        imports: list[ImportStatement] = []
        elements: list[CodeElement] = []

        try:
            for idx, line in enumerate(lines):
                line_num = idx + 1
                stripped = line.strip()
                if not stripped:
                    continue

                # Check imports
                for pat in _IMPORT_PATTERNS:
                    m = pat.match(stripped)
                    if m:
                        module = next((g for g in m.groups() if g), stripped)
                        imports.append(
                            ImportStatement(
                                module=module.strip(),
                                line_number=line_num,
                                raw_text=stripped,
                            )
                        )
                        break

                # Check class definition
                class_match = _CLASS_PATTERN.match(stripped)
                if class_match:
                    name = class_match.group(1)
                    # Heuristic end line: look for next empty or matching indent, or clamp
                    elements.append(
                        CodeElement(
                            name=name,
                            element_type="class",
                            start_line=line_num,
                            end_line=min(line_num + 30, total_lines),
                            content=line,
                        )
                    )
                    continue

                # Check function definition
                func_match = _FUNC_PATTERN.match(stripped)
                if func_match:
                    name = func_match.group(1)
                    elements.append(
                        CodeElement(
                            name=name,
                            element_type="function",
                            start_line=line_num,
                            end_line=min(line_num + 20, total_lines),
                            content=line,
                        )
                    )

        except Exception as e:
            logger.warning("Fallback parser encountered error on %s: %s", file_path, e)

        return ParsedFile(
            file_path=file_path,
            language=self.language,
            total_lines=total_lines,
            elements=elements,
            imports=imports,
            comments=[],
            metadata={"parser": "fallback"},
        )
