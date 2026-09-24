"""Semantic chunker for source code, preserving AST symbols and structural context."""

from backend.app.chunker.generic_chunker import GenericChunker
from backend.app.chunker.models import CodeChunk
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.parser.models import CodeElement, ParsedFile

logger = get_logger(__name__)


def _comment_prefix(language: str) -> str:
    """Return the single-line comment syntax for a language."""
    lang = language.lower()
    if lang in ("python", "py", "ruby", "sh", "bash", "yaml", "dockerfile"):
        return "#"
    return "//"


class SemanticChunker:
    """Chunks source code based on AST elements (classes, functions, methods)

    avoiding breaking functions while handling oversized elements gracefully.
    """

    def __init__(
        self,
        max_lines: int | None = None,
        min_lines: int | None = None,
        overlap_lines: int | None = None,
        max_chars: int | None = None,
    ) -> None:
        self.max_lines = max_lines or settings.CHUNK_MAX_LINES
        self.min_lines = min_lines or settings.CHUNK_MIN_LINES
        self.overlap_lines = overlap_lines or settings.CHUNK_OVERLAP_LINES
        self.max_chars = max_chars or settings.CHUNK_MAX_CHARS
        self.generic_chunker = GenericChunker(
            max_lines=self.max_lines,
            overlap_lines=self.overlap_lines,
        )

    def chunk_file(self, parsed: ParsedFile, raw_code: str) -> list[CodeChunk]:
        """Produce semantic code chunks from a ParsedFile and its original source text."""
        # If no AST elements were found, fall back to generic sliding-window chunking
        if not parsed.elements:
            return self.generic_chunker.chunk(
                code=raw_code,
                file_path=parsed.file_path,
                language=parsed.language,
                metadata={"chunk_strategy": "fallback_generic"},
            )

        lines = raw_code.splitlines(keepends=True)
        chunks: list[CodeChunk] = []

        # 1. Module header chunk (imports and module-level docstring/comments)
        header_chunk = self._create_module_header_chunk(parsed, lines)
        if header_chunk:
            chunks.append(header_chunk)

        # 2. Process top-level AST elements
        for elem in parsed.elements:
            elem_chunks = self._chunk_element(elem, lines, parsed)
            chunks.extend(elem_chunks)

        # 3. Handle uncovered code gaps between elements (e.g. top-level scripts)
        gap_chunks = self._capture_gaps(parsed, lines, chunks)
        chunks.extend(gap_chunks)

        # Sort all chunks chronologically by start_line
        chunks.sort(key=lambda c: (c.start_line, c.end_line))
        return chunks

    def _create_module_header_chunk(self, parsed: ParsedFile, lines: list[str]) -> CodeChunk | None:
        """Create a module header chunk capturing imports and initial docstrings/comments."""
        if not parsed.imports:
            return None

        # Determine span of module header
        last_import_line = max(imp.line_number for imp in parsed.imports)

        # Header ends at the last import or just before the first code element
        first_elem_line = (
            min(e.start_line for e in parsed.elements) if parsed.elements else last_import_line
        )

        header_end = min(last_import_line, first_elem_line - 1)
        if header_end < 1:
            header_end = last_import_line

        header_lines = lines[:header_end]
        content = "".join(header_lines).strip()
        if not content:
            return None

        return CodeChunk(
            file_path=parsed.file_path,
            language=parsed.language,
            content=content,
            start_line=1,
            end_line=header_end,
            chunk_type="module_header",
            symbol_name="<module>",
            parent_name=None,
            metadata={
                "imports_count": len(parsed.imports),
                "chunk_strategy": "module_header",
            },
        )

    def _chunk_element(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
    ) -> list[CodeChunk]:
        """Chunk a single AST element (class, function, method, interface)."""
        if elem.element_type in ("class", "struct"):
            return self._chunk_class(elem, lines, parsed)
        elif elem.element_type in ("function", "method"):
            return self._chunk_function(elem, lines, parsed)
        elif elem.element_type in ("interface", "type_alias"):
            return self._chunk_interface(elem, lines, parsed)
        else:
            return self._chunk_generic_element(elem, lines, parsed)

    def _chunk_class(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
    ) -> list[CodeChunk]:
        """Chunk a class. If small, chunk as whole. If large, create header and chunk methods."""
        line_count = elem.line_count
        char_count = len(elem.content)

        # If class fits within limit, keep it intact
        if line_count <= self.max_lines and char_count <= self.max_chars:
            return [
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=elem.content,
                    start_line=elem.start_line,
                    end_line=elem.end_line,
                    chunk_type="class",
                    symbol_name=elem.name,
                    parent_name=elem.parent_name,
                    metadata={
                        "methods_count": len(elem.children),
                        "docstring": elem.docstring,
                        "chunk_strategy": "whole_class",
                    },
                )
            ]

        # Class is large: emit class_header chunk + chunk each method
        chunks: list[CodeChunk] = []

        # Find header end: before first child method or first max_lines
        if elem.children:
            first_method_start = min(c.start_line for c in elem.children)
            header_end = max(elem.start_line, first_method_start - 1)
        else:
            header_end = min(elem.start_line + 25, elem.end_line)

        header_slice = lines[elem.start_line - 1 : header_end]
        header_content = "".join(header_slice).strip()

        if header_content:
            chunks.append(
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=header_content,
                    start_line=elem.start_line,
                    end_line=header_end,
                    chunk_type="class_header",
                    symbol_name=elem.name,
                    parent_name=elem.parent_name,
                    metadata={
                        "methods_count": len(elem.children),
                        "docstring": elem.docstring,
                        "chunk_strategy": "class_header",
                    },
                )
            )

        # Chunk each child method inside class
        for child in elem.children:
            method_chunks = self._chunk_function(
                child,
                lines,
                parsed,
                parent_class=elem.name,
            )
            chunks.extend(method_chunks)

        return chunks

    def _chunk_function(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
        parent_class: str | None = None,
    ) -> list[CodeChunk]:
        """Chunk a function or method.

        Avoid splitting when possible; perform windowed splitting with context
        headers if oversized.
        """
        line_count = elem.line_count
        char_count = len(elem.content)
        parent = parent_class or elem.parent_name
        chunk_type = "method" if parent else "function"

        # If function fits within max_lines and max_chars, keep it whole!
        if line_count <= self.max_lines and char_count <= self.max_chars:
            return [
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=elem.content,
                    start_line=elem.start_line,
                    end_line=elem.end_line,
                    chunk_type=chunk_type,
                    symbol_name=elem.name,
                    parent_name=parent,
                    metadata={
                        "docstring": elem.docstring,
                        "chunk_strategy": "whole_function",
                    },
                )
            ]

        # Function is too large: controlled splitting while preserving context
        return self._split_large_element(
            elem=elem,
            lines=lines,
            parsed=parsed,
            parent_name=parent,
            chunk_type=chunk_type,
        )

    def _chunk_interface(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
    ) -> list[CodeChunk]:
        """Chunk an interface or type definition."""
        if elem.line_count <= self.max_lines:
            return [
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=elem.content,
                    start_line=elem.start_line,
                    end_line=elem.end_line,
                    chunk_type=elem.element_type,
                    symbol_name=elem.name,
                    parent_name=elem.parent_name,
                    metadata={"chunk_strategy": f"whole_{elem.element_type}"},
                )
            ]
        return self._split_large_element(
            elem=elem,
            lines=lines,
            parsed=parsed,
            parent_name=elem.parent_name,
            chunk_type=elem.element_type,
        )

    def _chunk_generic_element(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
    ) -> list[CodeChunk]:
        """Default chunker for other code elements."""
        if elem.line_count <= self.max_lines:
            return [
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=elem.content,
                    start_line=elem.start_line,
                    end_line=elem.end_line,
                    chunk_type=elem.element_type,
                    symbol_name=elem.name,
                    parent_name=elem.parent_name,
                    metadata={"chunk_strategy": "whole_element"},
                )
            ]
        return self._split_large_element(
            elem=elem,
            lines=lines,
            parsed=parsed,
            parent_name=elem.parent_name,
            chunk_type=elem.element_type,
        )

    def _split_large_element(
        self,
        elem: CodeElement,
        lines: list[str],
        parsed: ParsedFile,
        parent_name: str | None,
        chunk_type: str,
    ) -> list[CodeChunk]:
        """Split a large function/element into overlapping windows with context headers."""
        elem_lines = lines[elem.start_line - 1 : elem.end_line]
        total_lines = len(elem_lines)
        step = max(1, self.max_lines - self.overlap_lines)

        comment_pfx = _comment_prefix(parsed.language)
        chunks: list[CodeChunk] = []
        start_idx = 0
        part_idx = 1

        # Calculate total parts upfront
        total_parts = max(1, (total_lines - self.overlap_lines + step - 1) // step)

        qual_symbol = f"{parent_name}.{elem.name}" if parent_name else elem.name

        while start_idx < total_lines:
            end_idx = min(start_idx + self.max_lines, total_lines)
            chunk_lines = elem_lines[start_idx:end_idx]
            raw_text = "".join(chunk_lines)

            # Prepend context header if this is a subsequent part
            if part_idx > 1:
                context_header = (
                    f"{comment_pfx} [Context: {qual_symbol} (part {part_idx}/{total_parts})]\n"
                )
                chunk_content = context_header + raw_text
            else:
                chunk_content = raw_text

            abs_start = elem.start_line + start_idx
            abs_end = elem.start_line + end_idx - 1

            chunks.append(
                CodeChunk(
                    file_path=parsed.file_path,
                    language=parsed.language,
                    content=chunk_content,
                    start_line=abs_start,
                    end_line=abs_end,
                    chunk_type=chunk_type,
                    symbol_name=elem.name,
                    parent_name=parent_name,
                    metadata={
                        "is_split": True,
                        "part_index": part_idx,
                        "total_parts": total_parts,
                        "docstring": elem.docstring if part_idx == 1 else None,
                        "chunk_strategy": "split_large_symbol",
                    },
                )
            )

            if end_idx >= total_lines:
                break

            start_idx += step
            part_idx += 1

        return chunks

    def _capture_gaps(
        self,
        parsed: ParsedFile,
        lines: list[str],
        existing_chunks: list[CodeChunk],
    ) -> list[CodeChunk]:
        """Detect and chunk uncovered code regions (e.g. top-level scripts or trailing code)."""
        if not existing_chunks:
            return []

        gap_chunks: list[CodeChunk] = []
        covered_ranges = sorted([(c.start_line, c.end_line) for c in existing_chunks])

        # Check gap before first chunk
        first_start = covered_ranges[0][0]
        if first_start > self.min_lines:
            gap_lines = lines[: first_start - 1]
            gap_text = "".join(gap_lines).strip()
            if gap_text and len(gap_lines) >= self.min_lines:
                gap_chunks.append(
                    CodeChunk(
                        file_path=parsed.file_path,
                        language=parsed.language,
                        content=gap_text,
                        start_line=1,
                        end_line=first_start - 1,
                        chunk_type="script_header",
                        metadata={"chunk_strategy": "gap_coverage"},
                    )
                )

        # Check gap after last chunk
        last_end = max(r[1] for r in covered_ranges)
        total_lines = len(lines)
        if total_lines - last_end >= self.min_lines:
            trailing_lines = lines[last_end:]
            trailing_text = "".join(trailing_lines).strip()
            if trailing_text:
                gap_chunks.append(
                    CodeChunk(
                        file_path=parsed.file_path,
                        language=parsed.language,
                        content=trailing_text,
                        start_line=last_end + 1,
                        end_line=total_lines,
                        chunk_type="script_trailer",
                        metadata={"chunk_strategy": "gap_coverage"},
                    )
                )

        return gap_chunks
